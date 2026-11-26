"""A version bump between offer and confirm is a conflict with alternatives."""

from pathlib import Path

from tests.fsm_helpers import DATE, DOCTOR, TIME
from tools.calendar import bump_version, execute_book, migrate, offer_slot, seed_slot


def test_stale_version_is_conflict_with_alternatives(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, (DOCTOR,))
    start = f"{DATE}T{TIME}:00-05:00"
    later = f"{DATE}T16:00:00-05:00"
    seed_slot(db, doctor_id=DOCTOR, start_iso=start, slot_id="S1", version=1)
    seed_slot(db, doctor_id=DOCTOR, start_iso=later, slot_id="S2", version=1)
    offered = offer_slot(db, doctor_id=DOCTOR, start_iso=start)
    assert offered.ok
    bump_version(db, "S1")
    result = execute_book(
        db,
        key="11111111-1111-4111-8111-111111111111:9",
        patient_name="Jordan Pike",
        phone="5550101234",
        doctor_id=DOCTOR,
        start_iso=start,
        offered_slot_id=offered.slot_id,
        offered_version=offered.version,
        slots_json={"doctor": DOCTOR},
    )
    assert result.ok is False
    assert result.conflict is True
    assert later in result.alternatives
