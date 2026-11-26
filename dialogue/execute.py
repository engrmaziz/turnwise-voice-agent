"""EXECUTE calls the calendar tool. Proposals never reach this module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dialogue.slots import DialogueState, confirmed_only
from tools.calendar import CalendarResult, execute_book, offer_slot


def idempotency_key(session_id: str, turn_id: int) -> str:
    return f"{session_id}:{turn_id}"


def start_iso_for(state: DialogueState, timezone: ZoneInfo) -> str:
    date = state.slots["date"].value
    time_s = state.slots["time"].value
    if len(time_s) == 4:
        time_s = f"0{time_s}"
    naive = datetime.fromisoformat(f"{date}T{time_s}:00")
    return naive.replace(tzinfo=timezone).isoformat()


def offer_booking(path: Path, state: DialogueState, timezone: ZoneInfo) -> CalendarResult:
    doctor = state.slots["doctor"].value
    start = start_iso_for(state, timezone)
    return offer_slot(path, doctor_id=doctor, start_iso=start)


def write_booking(
    path: Path,
    state: DialogueState,
    *,
    session_id: str,
    turn_id: int,
    timezone: ZoneInfo,
) -> CalendarResult:
    doctor = state.slots["doctor"].value
    start = start_iso_for(state, timezone)
    slots = confirmed_only(state.slots)
    if not slots:
        slots = {key: item.value for key, item in state.slots.items()}
    return execute_book(
        path,
        key=idempotency_key(session_id, turn_id),
        patient_name=state.slots["patient_name"].value,
        phone=state.slots["phone"].value,
        doctor_id=doctor,
        start_iso=start,
        offered_slot_id=state.offered_slot_id,
        offered_version=state.offered_version,
        slots_json=slots,
    )
