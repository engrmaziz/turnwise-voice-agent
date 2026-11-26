"""Task success is a database and state compare. Soft scores cannot flip it."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from evals.caller_scripted import resolve_roster_doctor
from evals.harness import RunTrace
from evals.schema import Scenario
from nlp.hotwords import load_roster
from server.config import Settings
from tools.faq import load_chunks, retrieve


class DbJudgement:
    __slots__ = ("actual", "appointment_id", "expected", "reason", "success")

    def __init__(
        self,
        *,
        success: bool,
        reason: str,
        appointment_id: str | None,
        expected: dict[str, str],
        actual: dict[str, str],
    ) -> None:
        self.success = success
        self.reason = reason
        self.appointment_id = appointment_id
        self.expected = expected
        self.actual = actual


def judge(
    scenario: Scenario,
    trace: RunTrace,
    *,
    settings: Settings | None = None,
) -> DbJudgement:
    resolved = settings if settings is not None else Settings()
    if scenario.goal == "book":
        return _book(scenario, trace, resolved)
    if scenario.goal == "urgent":
        return _urgent(scenario, trace)
    if scenario.goal == "faq":
        return _faq(scenario, trace, resolved)
    if scenario.goal == "handoff":
        return _handoff(trace)
    if scenario.goal == "cancel":
        return _cancel(trace)
    if scenario.goal == "reschedule":
        return _reschedule(scenario, trace, resolved)
    if scenario.goal == "check":
        return _check(trace)
    return DbJudgement(
        success=False,
        reason="unknown_goal",
        appointment_id=None,
        expected={},
        actual={},
    )


def _book(scenario: Scenario, trace: RunTrace, settings: Settings) -> DbJudgement:
    roster = load_roster(Path(settings.doctor_roster_path))
    doctor = resolve_roster_doctor(scenario.slots.get("doctor", ""), roster, settings)
    date = scenario.slots.get("date", "")
    time_s = scenario.slots.get("time", "")
    timezone = ZoneInfo(settings.clinic_timezone)
    expected_start = ""
    if date and time_s:
        expected_start = (
            datetime.fromisoformat(f"{date}T{time_s}:00").replace(tzinfo=timezone).isoformat()
        )
    expected = {"doctor": doctor, "start_iso": expected_start}
    if not trace.appointments:
        return DbJudgement(
            success=False,
            reason="no_appointment",
            appointment_id=None,
            expected=expected,
            actual={},
        )
    row = trace.appointments[0]
    actual = {"doctor": row["doctor_id"], "start_iso": row["start_iso"]}
    if row["status"] != "booked":
        return DbJudgement(
            success=False,
            reason="not_booked",
            appointment_id=row["id"],
            expected=expected,
            actual=actual,
        )
    if doctor and row["doctor_id"] != doctor:
        return DbJudgement(
            success=False,
            reason="wrong_doctor",
            appointment_id=row["id"],
            expected=expected,
            actual=actual,
        )
    if expected_start and row["start_iso"] != expected_start:
        return DbJudgement(
            success=False,
            reason="wrong_time",
            appointment_id=row["id"],
            expected=expected,
            actual=actual,
        )
    stored = _slots_json(row)
    for key in ("doctor", "date", "time"):
        want = scenario.slots.get(key, "")
        if key == "doctor":
            want = doctor
        got = stored.get(key, "")
        if key == "doctor" and got and got != want:
            return DbJudgement(
                success=False,
                reason="yes_to_wrong_readback",
                appointment_id=row["id"],
                expected=expected,
                actual={**actual, **stored},
            )
        confirmed = trace.confirmed.get(key, "")
        if confirmed and key == "doctor" and confirmed != want:
            return DbJudgement(
                success=False,
                reason="yes_to_wrong_readback",
                appointment_id=row["id"],
                expected=expected,
                actual={**actual, "confirmed_doctor": confirmed},
            )
    return DbJudgement(
        success=True,
        reason="booked",
        appointment_id=row["id"],
        expected=expected,
        actual=actual,
    )


def _urgent(scenario: Scenario, trace: RunTrace) -> DbJudgement:
    ok = trace.state_id == "URGENT" and not trace.appointments
    return DbJudgement(
        success=ok,
        reason="urgent" if ok else "not_urgent",
        appointment_id=None,
        expected={"state": "URGENT", "appointments": "0"},
        actual={"state": trace.state_id, "appointments": str(len(trace.appointments))},
    )


def _faq(scenario: Scenario, trace: RunTrace, settings: Settings) -> DbJudgement:
    query = scenario.slots.get("faq_query") or (scenario.script[0] if scenario.script else "")
    chunks = load_chunks(Path(settings.faq_path))
    hit = retrieve(query, chunks, min_score=settings.faq_min_score)
    refusal = trace.last_template == "faq_refuse" or trace.last_action == "say_faq_refuse"
    if hit is None:
        ok = refusal and not trace.faq_chunk_id
        return DbJudgement(
            success=ok,
            reason="faq_refuse" if ok else "faq_should_refuse",
            appointment_id=None,
            expected={"chunk": "", "refuse": "1"},
            actual={"chunk": trace.faq_chunk_id, "refuse": "1" if refusal else "0"},
        )
    ok = bool(trace.faq_chunk_id) and not refusal and trace.ungrounded == 0
    return DbJudgement(
        success=ok,
        reason="faq_grounded" if ok else "faq_ungrounded",
        appointment_id=None,
        expected={"chunk": hit.chunk_id},
        actual={"chunk": trace.faq_chunk_id, "template": trace.last_template},
    )


def _handoff(trace: RunTrace) -> DbJudgement:
    ok = trace.state_id == "HANDOFF"
    return DbJudgement(
        success=ok,
        reason="handoff" if ok else "not_handoff",
        appointment_id=None,
        expected={"state": "HANDOFF"},
        actual={"state": trace.state_id, "summary": trace.played_text},
    )


def _cancel(trace: RunTrace) -> DbJudgement:
    if not trace.appointments:
        return DbJudgement(
            success=True,
            reason="no_row_to_cancel",
            appointment_id=None,
            expected={"status": "cancelled_or_absent"},
            actual={},
        )
    row = trace.appointments[0]
    ok = row["status"] == "cancelled"
    return DbJudgement(
        success=ok,
        reason="cancelled" if ok else "still_booked",
        appointment_id=row["id"],
        expected={"status": "cancelled"},
        actual={"status": row["status"]},
    )


def _reschedule(scenario: Scenario, trace: RunTrace, settings: Settings) -> DbJudgement:
    if not trace.appointments:
        return DbJudgement(
            success=False,
            reason="no_appointment",
            appointment_id=None,
            expected=dict(scenario.slots),
            actual={},
        )
    return _book(scenario, trace, settings)


def _check(trace: RunTrace) -> DbJudgement:
    ok = bool(trace.appointments) or trace.state_id in {"CLOSE", "COLLECT_SLOTS", "CONFIRM"}
    return DbJudgement(
        success=ok,
        reason="checked" if ok else "check_miss",
        appointment_id=trace.appointments[0]["id"] if trace.appointments else None,
        expected={},
        actual={"state": trace.state_id},
    )


def _slots_json(row: dict[str, str]) -> dict[str, str]:
    raw = row.get("slots_json") or "{}"
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in loaded.items()}
