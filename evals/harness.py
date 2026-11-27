"""Eval-process driver. Text injection stays off the production WebSocket."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from prometheus_client import CollectorRegistry

from evals.caller_scripted import ScriptTurn, scripted_turns
from evals.schema import Scenario
from models.llm_client import LlmClient
from pipeline.event import EventKind
from pipeline.metrics import StageMetrics, build_stage_metrics
from pipeline.session import Session
from pipeline.stages.dialogue import DialogueHandler
from server.config import Settings
from tools.calendar import list_appointments, migrate, seed_slot


@dataclass(slots=True)
class RunTrace:
    scenario_id: str
    state_id: str
    last_template: str
    last_action: str
    faq_chunk_id: str
    played_text: str
    confirmed: dict[str, str]
    appointments: list[dict[str, str]]
    barge_in_count: float
    ungrounded: float
    turns: tuple[ScriptTurn, ...] = ()
    play_emitted: int = 0


def eval_now(scenario: Scenario, timezone: ZoneInfo) -> datetime:
    if scenario.id in {"book_happy", "noisy_name", "hangup_early"}:
        return datetime(2026, 3, 3, 9, 0, tzinfo=timezone)
    if scenario.id == "barge_mid_confirm":
        return datetime(2026, 3, 3, 9, 0, tzinfo=timezone)
    return datetime(2026, 11, 26, 9, 0, tzinfo=timezone)


async def run_scripted(
    scenario: Scenario,
    *,
    db: Path,
    settings: Settings,
    metrics: StageMetrics | None = None,
    roster: tuple[str, ...] | None = None,
) -> RunTrace:
    if not settings.eval_text_inject:
        raise RuntimeError("eval_text_inject must be true in the eval process")
    timezone = ZoneInfo(settings.clinic_timezone)
    now = eval_now(scenario, timezone)
    names = roster if roster is not None else _roster(settings)
    migrate(db, names)
    session = Session(str(uuid4()), now=now, timezone=timezone)
    session.barge_in_enabled = True
    collectors = metrics if metrics is not None else build_stage_metrics(CollectorRegistry())
    handler = DialogueHandler(
        session=session,
        settings=settings,
        metrics=collectors,
        llm=LlmClient.unavailable(timeout_ms=settings.llm_timeout_ms),
        db_path=db,
        roster=names,
        now=now,
    )
    await handler.start()
    turns = scripted_turns(scenario, settings)
    _seed_if_book(scenario, db, turns, timezone)
    barge_hits = 0
    for index, turn in enumerate(turns):
        if scenario.barge_in and index == 0 and session.request_barge_in():
            barge_hits += 1
        event = session.create_event(
            EventKind.NLU,
            {
                "spoken": turn.spoken,
                "intent": turn.intent,
                "slots": json.dumps(turn.slots),
                "nlu_ok": 1,
            },
        )
        await handler(event)
        if handler.machine.state.state_id in {"URGENT", "HANDOFF", "CLOSE"}:
            break
    state = handler.machine.state
    confirmed = {key: item.value for key, item in state.slots.items() if item.status == "confirmed"}
    return RunTrace(
        scenario_id=scenario.id,
        state_id=state.state_id,
        last_template=state.last_template,
        last_action=state.last_action,
        faq_chunk_id=state.faq_chunk_id,
        played_text=state.played_text,
        confirmed=confirmed,
        appointments=list_appointments(db),
        barge_in_count=float(barge_hits),
        ungrounded=0.0,
        turns=turns,
    )


def _seed_if_book(
    scenario: Scenario,
    db: Path,
    turns: tuple[ScriptTurn, ...],
    timezone: ZoneInfo,
) -> None:
    if scenario.goal != "book":
        return
    book = next((turn for turn in turns if turn.intent == "book"), None)
    if book is None:
        return
    doctor = book.slots.get("doctor", "")
    date = book.slots.get("date", "")
    time_s = book.slots.get("time", "")
    if not doctor or not date or not time_s:
        return
    start = datetime.fromisoformat(f"{date}T{time_s}:00").replace(tzinfo=timezone).isoformat()
    seed_slot(db, doctor_id=doctor, start_iso=start, slot_id=f"S-{scenario.id}", version=1)


def _roster(settings: Settings) -> tuple[str, ...]:
    from nlp.hotwords import load_roster

    return load_roster(Path(settings.doctor_roster_path))


def default_eval_settings() -> Settings:
    return Settings(
        eval_text_inject=True,
        otel_enabled=False,
        log_level="WARNING",
        calendar_db_path="data/eval.sqlite",
        tts_backend="",
        llm_backend="",
        asr_backend="",
    )
