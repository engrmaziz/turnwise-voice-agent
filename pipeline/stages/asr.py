"""Streaming ASR stage. Partials stay spoken; ITN and temporal run on finals only."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from opentelemetry.trace import get_current_span

from models.asr_pool import AsrPool, AsrStream
from models.asr_types import AsrHypothesis
from nlp.hotwords import hotwords_for, load_roster
from nlp.itn import inverse_normalize
from nlp.slot_confidence import slot_confidence
from nlp.temporal import resolve
from pipeline.event import Event, EventKind, JsonValue
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings

_LOG = structlog.get_logger("pipeline.stages.asr")

Forward = Callable[[Event], Awaitable[None]]


class AsrHandler:
    """One instance per call. A barge-in generation change drops the stream."""

    __slots__ = (
        "_engine",
        "_expected_vocab_id",
        "_forward",
        "_hotwords",
        "_metrics",
        "_roster",
        "_session",
        "_settings",
        "_stream",
        "_zone",
        "finals",
        "partials",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        engine: AsrPool,
        metrics: StageMetrics,
        forward: Forward | None = None,
        roster: tuple[str, ...] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._engine = engine
        self._metrics = metrics
        self._forward = forward
        self._zone = ZoneInfo(settings.clinic_timezone)
        if roster is not None:
            self._roster = roster
        else:
            self._roster = load_roster(Path(settings.doctor_roster_path))
        self._hotwords = hotwords_for(
            session.expected_vocab_id,
            clinic_name=settings.clinic_name,
            doctors=self._roster,
        )
        self._expected_vocab_id = session.expected_vocab_id
        self._stream: AsrStream | None = None
        self.partials = 0
        self.finals = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    @property
    def hotwords(self) -> tuple[str, ...]:
        return tuple(self._hotwords)

    @property
    def applied_hotwords(self) -> tuple[str, ...]:
        stream = self._stream
        if stream is None:
            return ()
        return stream.hotwords

    async def __call__(self, event: Event) -> None:
        if event.kind is EventKind.SESSION_END or event.kind is EventKind.TURN_END:
            await self._finish(event)
            return
        if event.kind is not EventKind.AUDIO or event.frame_index is None:
            return
        pcm = self._session.get_pcm(event.frame_index)
        if pcm is None:
            return
        if len(pcm) % 2 != 0:
            raise ValueError("asr pcm length must be even")
        self._sync_hotwords()
        stream = self._ensure_stream()
        try:
            hypothesis = await stream.push(pcm)
        except TimeoutError:
            self._stream = None
            await self._timeout_final(event)
            return
        if hypothesis is None:
            return
        if hypothesis.stable_prefix:
            lag = max(0.0, time.perf_counter() - event.ts_monotonic)
            self._metrics.asr_stable_lag.observe(lag)
        await self._emit_partial(event, hypothesis)

    def _ensure_stream(self) -> AsrStream:
        current = self._stream
        if current is not None and current.generation == self._session.generation:
            return current
        stream = self._engine.start_stream(
            self._session.session_id,
            self._session.generation,
            live=lambda: self._session.generation,
            speaking=lambda: self._session.speaking_task_count > 0,
        )
        if stream.supports_hotwords:
            stream.set_hotwords(self._hotwords, self._settings.hotword_score)
        self._stream = stream
        return stream

    def _sync_hotwords(self) -> None:
        vocab = self._session.expected_vocab_id
        if vocab == self._expected_vocab_id:
            return
        self._expected_vocab_id = vocab
        self._hotwords = hotwords_for(
            vocab,
            clinic_name=self._settings.clinic_name,
            doctors=self._roster,
        )
        self._metrics.hotword_updates.inc()
        stream = self._stream
        if stream is not None and stream.supports_hotwords:
            stream.set_hotwords(self._hotwords, self._settings.hotword_score)

    async def _emit_partial(self, event: Event, hypothesis: AsrHypothesis) -> None:
        self.partials += 1
        span = get_current_span()
        span.set_attribute("model", self._engine.backend)
        payload: dict[str, JsonValue] = {"spoken": hypothesis.text}
        partial = self._session.create_event(
            EventKind.PARTIAL,
            payload,
            frame_index=event.frame_index,
        )
        if self._forward is not None:
            await self._forward(partial)

    async def _finish(self, event: Event) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        started = time.perf_counter()
        try:
            hypothesis = await stream.finish()
        except TimeoutError:
            await self._timeout_final(event)
            return
        self._metrics.asr_finalize.observe(time.perf_counter() - started)
        if hypothesis is None:
            return
        await self._emit_final(event, hypothesis, asr_ok=True)

    async def _timeout_final(self, event: Event) -> None:
        empty = AsrHypothesis(
            text="",
            words=(),
            stable_prefix="",
            generation=self._session.generation,
            is_final=True,
        )
        await self._emit_final(event, empty, asr_ok=False)

    async def _emit_final(self, event: Event, hypothesis: AsrHypothesis, *, asr_ok: bool) -> None:
        self.finals += 1
        spoken = hypothesis.text
        itn_started = time.perf_counter()
        itn = await inverse_normalize(spoken, timeout_s=self._settings.itn_timeout_s)
        self._metrics.itn_seconds.observe(time.perf_counter() - itn_started)
        if not itn.ok:
            self._metrics.itn_errors.inc()
        temporal_started = time.perf_counter()
        grounded = resolve(itn.normalized if itn.ok else spoken, self._session.now, self._zone)
        self._metrics.temporal_seconds.observe(time.perf_counter() - temporal_started)
        if grounded.unresolved:
            self._metrics.temporal_unresolved.inc()
        conf = slot_confidence(hypothesis.words, 0, len(spoken)) if spoken else 0.0
        span = get_current_span()
        span.set_attribute("model", self._engine.backend)
        payload: dict[str, JsonValue] = {
            "spoken": spoken,
            "normalized": itn.normalized,
            "normalized_ok": 1 if itn.ok else 0,
            "asr_ok": 1 if asr_ok else 0,
            "instants": json.dumps(list(grounded.instants)),
            "slot_conf": json.dumps(conf),
            "ambiguous": 1 if grounded.ambiguous else 0,
            "needs_confirm": 1 if grounded.needs_confirm else 0,
        }
        final = self._session.create_event(EventKind.FINAL, payload, frame_index=event.frame_index)
        _LOG.info(
            "asr_final",
            session_id=self._session.session_id,
            asr_ok=asr_ok,
            normalized_ok=itn.ok,
        )
        if self._forward is not None:
            await self._forward(final)
