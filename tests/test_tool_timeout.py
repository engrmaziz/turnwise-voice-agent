"""A 2 s tool hits the 1500 ms hard timeout. One retry uses the same key."""

import asyncio
from pathlib import Path

from dialogue.context import StepContext
from dialogue.execute import idempotency_key
from dialogue.slots import DialogueState
from tests.fsm_helpers import DATE, DOCTOR, TIME, make_machine
from tools.calendar import appointment_count, execute_book, migrate, seed_slot
from tools.timeouts import run_with_filler


async def test_two_second_sleep_hits_hard_timeout() -> None:
    async def slow() -> str:
        await asyncio.sleep(2.0)
        return "late"

    outcome = await run_with_filler(slow(), filler_s=0.3, hard_s=1.5)
    assert outcome.timed_out is True
    assert outcome.value is None
    assert outcome.filler is True


def test_retry_same_key_never_writes_two_rows(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, (DOCTOR,))
    start = f"{DATE}T{TIME}:00-05:00"
    seed_slot(db, doctor_id=DOCTOR, start_iso=start, slot_id="S1", version=1)
    key = idempotency_key("11111111-1111-4111-8111-111111111111", 4)
    first = execute_book(
        db,
        key=key,
        patient_name="Jordan Pike",
        phone="5550101234",
        doctor_id=DOCTOR,
        start_iso=start,
        offered_slot_id="S1",
        offered_version=1,
        slots_json={"doctor": DOCTOR},
    )
    second = execute_book(
        db,
        key=key,
        patient_name="Jordan Pike",
        phone="5550101234",
        doctor_id=DOCTOR,
        start_iso=start,
        offered_slot_id="S1",
        offered_version=1,
        slots_json={"doctor": DOCTOR},
    )
    assert first.appointment_id == second.appointment_id
    assert appointment_count(db) in {0, 1}
    assert appointment_count(db) == 1


def test_second_tool_error_hands_off() -> None:
    machine = make_machine()
    machine.state = DialogueState(state_id="EXECUTE", tool_tries=0)
    machine.step(StepContext(event="tool_error", settings=machine.settings))
    assert machine.state.state_id == "EXECUTE"
    assert machine.state.tool_tries == 1
    machine.step(StepContext(event="tool_error", settings=machine.settings))
    assert machine.state.state_id == "HANDOFF"
