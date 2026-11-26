"""Spoken NLU stage. Reads FINAL.spoken, never normalized."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import structlog
from opentelemetry.trace import get_current_span

from models.nlu_pool import NluHypothesis, NluScorer, NluUnavailableError
from nlp.disfluency import SlotSpan, apply_repairs
from nlp.hotwords import load_roster
from nlp.nlu_features import tokenize
from nlp.phonetic import resolve_entity
from pipeline.event import Event, EventKind, JsonValue
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.nlu")

Forward = Callable[[Event], Awaitable[None]]


class NluHandler:
    """One instance per call. Timeouts emit ``nlu_ok=0`` with no regex fallback."""

    __slots__ = (
        "_forward",
        "_metrics",
        "_roster",
        "_scorer",
        "_session",
        "_settings",
        "emitted",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        scorer: NluScorer,
        metrics: StageMetrics,
        forward: Forward | None = None,
        roster: tuple[str, ...] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._scorer = scorer
        self._metrics = metrics
        self._forward = forward
        if roster is not None:
            self._roster = roster
        else:
            self._roster = load_roster(Path(settings.doctor_roster_path))
        self.emitted = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.FINAL:
            return
        spoken = event.payload.get("spoken")
        text = spoken if isinstance(spoken, str) else ""
        started = time.perf_counter()
        try:
            hypo = await self._scorer.predict(text)
        except TimeoutError:
            self._metrics.nlu_reject.inc()
            get_current_span().set_attribute("model", self._scorer.model_name)
            await self._emit(event, nlu_ok=0, hypo=None, spans=(), repairs=0)
            return
        except NluUnavailableError:
            self._metrics.nlu_reject.inc()
            get_current_span().set_attribute("model", self._scorer.model_name)
            await self._emit(event, nlu_ok=0, hypo=None, spans=(), repairs=0)
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._metrics.nlu_seconds.observe(elapsed_ms / 1000.0)
        span = get_current_span()
        span.set_attribute("model", self._scorer.model_name)
        span.set_attribute("latency_ms", elapsed_ms)
        tokens = list(hypo.tokens) if hypo.tokens else tokenize(text)
        tags = list(hypo.tags)
        spans, repairs = apply_repairs(tokens, tags, self._settings)
        if repairs:
            self._metrics.repair_applied.inc()
        await self._emit(event, nlu_ok=1, hypo=hypo, spans=tuple(spans), repairs=repairs)

    async def _emit(
        self,
        event: Event,
        *,
        nlu_ok: int,
        hypo: NluHypothesis | None,
        spans: tuple[SlotSpan, ...],
        repairs: int,
    ) -> None:
        slots: dict[str, str] = {}
        candidates: list[str] = []
        for span in spans:
            if span.slot == "doctor":
                resolved = resolve_entity(span.text, list(self._roster), self._settings)
                if resolved.entity_id is None:
                    self._metrics.disambiguation.inc()
                    candidates = list(resolved.candidates)
                    continue
                slots["doctor"] = resolved.entity_id
                continue
            slots[span.slot] = span.text
        payload: dict[str, JsonValue] = {
            "spoken": str(event.payload.get("spoken") or ""),
            "nlu_ok": nlu_ok,
            "intent": hypo.intent if hypo is not None else "",
            "intent_p": hypo.intent_confidence if hypo is not None else 0.0,
            "slots": json.dumps(slots),
            "doctor_candidates": json.dumps(candidates),
            "repairs": repairs,
        }
        tracer = self._session.tracer
        if tracer is not None:
            self._session.turn_span.mark(tracer, "nlu")
        nlu = self._session.create_event(EventKind.NLU, payload, frame_index=event.frame_index)
        self.emitted += 1
        _LOG.info(
            "nlu",
            session_id=self._session.session_id,
            nlu_ok=nlu_ok,
            intent=payload["intent"],
        )
        if self._forward is not None:
            await self._forward(nlu)
