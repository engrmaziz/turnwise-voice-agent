"""Dialogue stage. The FSM is the only writer of dialogue state and the calendar."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from opentelemetry.trace import get_current_span

from dialogue.confirm import needs_explicit_confirm
from dialogue.context import StepContext
from dialogue.execute import offer_booking, write_booking
from dialogue.filler import filler_event
from dialogue.machine import DialogueMachine
from dialogue.planner import speak
from dialogue.slots import DialogueState, next_ask_slot
from models.llm_client import LlmClient
from nlp.hotwords import load_roster
from pipeline.event import Event, EventKind, JsonValue
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from server.config import Settings
from tools.calendar import CalendarError, CalendarResult, migrate
from tools.faq import load_chunks, retrieve
from tools.timeouts import run_with_filler

_LOG = structlog.get_logger("pipeline.stages.dialogue")

Forward = Callable[[Event], Awaitable[None]]


class DialogueHandler:
    """One instance per call. Starts in GREET and emits SAY templates."""

    __slots__ = (
        "_chunks",
        "_db",
        "_forward",
        "_llm",
        "_machine",
        "_metrics",
        "_migrated",
        "_session",
        "_settings",
        "_started",
        "emitted",
    )

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        metrics: StageMetrics,
        llm: LlmClient,
        forward: Forward | None = None,
        db_path: Path | None = None,
        roster: tuple[str, ...] | None = None,
        now: datetime | None = None,
    ) -> None:
        roster_names = (
            roster if roster is not None else load_roster(Path(settings.doctor_roster_path))
        )
        timezone = ZoneInfo(settings.clinic_timezone)
        clock = now if now is not None else session.now
        self._session = session
        self._settings = settings
        self._metrics = metrics
        self._llm = llm
        self._forward = forward
        self._machine = DialogueMachine(
            settings=settings,
            roster=roster_names,
            timezone=timezone,
            now=clock,
            on_reject=lambda guard: metrics.fsm_rejects.labels(guard=str(guard)).inc(),
            on_transition=lambda src, dst: _on_transition(metrics, str(src), str(dst)),
        )
        self._db = db_path if db_path is not None else Path(settings.calendar_db_path)
        self._chunks = load_chunks(Path(settings.faq_path))
        self._started = False
        self._migrated = False
        self.emitted = 0

    def set_forward(self, forward: Forward) -> None:
        self._forward = forward

    @property
    def machine(self) -> DialogueMachine:
        return self._machine

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._machine.start()
        await self._say(self._machine.state)

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.NLU:
            return
        if not self._started:
            await self.start()
        spoken = str(event.payload.get("spoken") or "")
        intent = str(event.payload.get("intent") or "")
        nlu_ok = int(event.payload.get("nlu_ok") or 0)
        slots = _slots_from_payload(event.payload.get("slots"))
        if nlu_ok == 0 and self._settings.regex_slots_enabled:
            from dialogue.regex_slots import match_slots

            slots = {**match_slots(spoken, self._machine.roster), **slots}
        started = time.perf_counter()
        span = get_current_span()
        span.set_attribute("model", "fsm")
        state = self._machine.nlu(spoken=spoken, intent=intent, slots=slots)
        self._count_policy(state)
        state = await self._after(state)
        span.set_attribute("latency_ms", (time.perf_counter() - started) * 1000.0)
        await self._say(state)

    async def _after(self, state: DialogueState) -> DialogueState:
        if state.state_id == "FAQ" and state.last_action == "faq_enter":
            query = str(state.slots["faq_query"].value) if "faq_query" in state.slots else ""
            if not query:
                query = state.played_text
            hit = retrieve(query, self._chunks, min_score=self._settings.faq_min_score)
            if hit is None:
                return self._machine.step(
                    StepContext(
                        event="faq_miss",
                        settings=self._settings,
                        roster=self._machine.roster,
                        now=self._machine.now,
                        timezone=self._machine.timezone,
                    )
                )
            return self._machine.step(
                StepContext(
                    event="faq_hit",
                    faq_chunk_id=hit.chunk_id,
                    faq_reply=hit.reply,
                    settings=self._settings,
                    roster=self._machine.roster,
                    now=self._machine.now,
                    timezone=self._machine.timezone,
                )
            )
        if state.last_action == "confirm" and state.intent == "book":
            self._ensure_db()
            try:
                offered = await self._calendar_call(
                    offer_booking, self._db, state, self._machine.timezone
                )
            except CalendarError:
                self._metrics.calendar_errors.inc()
                return state
            if offered.ok:
                updated = state.model_copy(
                    update={
                        "offered_slot_id": offered.slot_id,
                        "offered_version": offered.version,
                    }
                )
                self._machine.state = updated
                return updated
        if state.state_id == "EXECUTE" and state.last_action == "execute":
            self._ensure_db()
            return await self._run_tool(state)
        return state

    def _count_policy(self, state: DialogueState) -> None:
        if state.last_action == "confirm":
            for key, item in state.slots.items():
                if needs_explicit_confirm(key, item.confidence, self._settings):
                    self._metrics.confirm_explicit.inc()
                    break
        if state.last_action == "repair":
            slot = next_ask_slot(state.intent, state.slots) or "date"
            self._metrics.repair_total.labels(slot=slot).inc()

    async def _calendar_call(
        self,
        fn: object,
        *args: object,
        **kwargs: object,
    ) -> CalendarResult:
        started = time.perf_counter()
        try:
            return await _to_thread(fn, *args, **kwargs)
        finally:
            self._metrics.calendar_seconds.observe(time.perf_counter() - started)

    def _ensure_db(self) -> None:
        if self._migrated:
            return
        migrate(self._db, self._machine.roster)
        self._migrated = True

    async def _run_tool(self, state: DialogueState) -> DialogueState:
        async def on_filler() -> None:
            self._metrics.tool_filler.inc()
            if self._forward is not None:
                await self._forward(filler_event(self._session))

        async def invoke() -> CalendarResult:
            return await self._calendar_call(
                write_booking,
                self._db,
                self._machine.state,
                session_id=self._session.session_id,
                turn_id=self._session.turn_id,
                timezone=self._machine.timezone,
            )

        filler_s = self._settings.tool_filler_after_ms / 1000.0
        hard_s = self._settings.tool_hard_timeout_ms / 1000.0
        try:
            outcome = await run_with_filler(
                invoke(), filler_s=filler_s, hard_s=hard_s, on_filler=on_filler
            )
        except CalendarError:
            self._metrics.calendar_errors.inc()
            outcome_value = None
            timed_out = False
            filler = False
        else:
            outcome_value = outcome.value
            timed_out = outcome.timed_out
            filler = outcome.filler
        if filler:
            self._machine.state = self._machine.state.model_copy(update={"say_filler": 1})
        if timed_out or outcome_value is None:
            self._metrics.tool_retries.inc()
            return self._machine.step(
                StepContext(
                    event="tool_error",
                    settings=self._settings,
                    roster=self._machine.roster,
                    now=self._machine.now,
                    timezone=self._machine.timezone,
                )
            )
        if outcome_value.conflict:
            self._metrics.calendar_conflicts.inc()
            return self._machine.step(
                StepContext(
                    event="tool_conflict",
                    conflict_alts=outcome_value.alternatives,
                    settings=self._settings,
                    roster=self._machine.roster,
                    now=self._machine.now,
                    timezone=self._machine.timezone,
                )
            )
        if outcome_value.ok:
            return self._machine.step(
                StepContext(
                    event="tool_ok",
                    appointment_id=outcome_value.appointment_id,
                    settings=self._settings,
                    roster=self._machine.roster,
                    now=self._machine.now,
                    timezone=self._machine.timezone,
                )
            )
        return self._machine.step(
            StepContext(
                event="tool_error",
                settings=self._settings,
                roster=self._machine.roster,
                now=self._machine.now,
                timezone=self._machine.timezone,
            )
        )

    async def _say(self, state: DialogueState) -> None:
        template_id = state.last_template or "greet"
        text = await speak(
            template_id,
            fallback=state.played_text or template_id,
            settings=self._settings,
            llm=self._llm,
            paraphrase=False,
        )
        payload: dict[str, JsonValue] = {
            "template_id": template_id.split(":")[0],
            "text": text,
            "filler": state.say_filler,
            "state": state.state_id,
        }
        if state.faq_chunk_id:
            payload["chunk_id"] = state.faq_chunk_id
        event = self._session.create_event(EventKind.SAY, payload)
        self.emitted += 1
        _LOG.info(
            "say",
            session_id=self._session.session_id,
            template_id=payload["template_id"],
            state=state.state_id,
        )
        if self._forward is not None:
            await self._forward(event)


def _on_transition(metrics: StageMetrics, src: str, dst: str) -> None:
    metrics.fsm_transitions.labels(state=src, next=dst).inc()
    if dst == "URGENT" and src != "URGENT":
        metrics.urgent_keyword.inc()
    if dst == "HANDOFF" and src != "HANDOFF":
        metrics.handoff_total.labels(reason="fsm").inc()


def _slots_from_payload(raw: object) -> dict[str, str]:
    if isinstance(raw, str) and raw:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return {str(k): str(v) for k, v in loaded.items()}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


async def _to_thread(fn: object, *args: object, **kwargs: object) -> CalendarResult:
    import asyncio

    if not callable(fn):
        raise CalendarError("missing callable")

    def bound() -> CalendarResult:
        result = fn(*args, **kwargs)
        if not isinstance(result, CalendarResult):
            raise CalendarError("bad result")
        return result

    return await asyncio.to_thread(bound)
