"""Two executes with the same key insert one appointment."""

from pathlib import Path

from dialogue.execute import idempotency_key
from tests.fsm_helpers import DATE, DOCTOR, TIME
from tools.calendar import appointment_count, execute_book, migrate, seed_slot


def test_second_execute_returns_the_first_row(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, (DOCTOR,))
    start = f"{DATE}T{TIME}:00-05:00"
    seed_slot(db, doctor_id=DOCTOR, start_iso=start, slot_id="S1", version=1)
    key = idempotency_key("11111111-1111-4111-8111-111111111111", 1)
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
    assert first.ok
    assert second.ok
    assert first.appointment_id == second.appointment_id
    assert appointment_count(db) == 1
