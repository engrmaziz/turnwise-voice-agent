"""Book and cancel required slots. Past dates are invalid."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dialogue.slots import SlotValue, missing_required, required_for_intent
from dialogue.validators import validate_date, validate_doctor, validate_phone


def test_book_requires_core_slots() -> None:
    required = required_for_intent("book", {})
    assert required == {"patient_name", "phone", "doctor", "date", "time"}


def test_cancel_accepts_appointment_id_or_triple() -> None:
    by_id = required_for_intent("cancel", {"appointment_id": SlotValue(value="A1001")})
    assert by_id == {"appointment_id"}
    by_triple = required_for_intent("cancel", {})
    assert by_triple == {"patient_name", "phone", "date"}
    missing = missing_required("cancel", {"patient_name": SlotValue(value="Ada")})
    assert "phone" in missing
    assert "date" in missing


def test_past_date_is_invalid() -> None:
    today = datetime(2026, 11, 26, tzinfo=ZoneInfo("America/New_York")).date()
    assert validate_date("2026-11-25", today=today) is not None
    assert validate_date("2026-12-15", today=today) is None


def test_doctor_must_be_roster_id() -> None:
    assert validate_doctor("Lan", ("Dr. Avery Lang",)) is not None
    assert validate_doctor("Dr. Avery Lang", ("Dr. Avery Lang",)) is None


def test_phone_ten_digits() -> None:
    assert validate_phone("5550101234") is None
    assert validate_phone("123") is not None


def test_validators_do_not_call_the_llm() -> None:
    text = Path("dialogue/validators.py").read_text(encoding="utf-8")
    imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
    assert not any("llm" in line.casefold() for line in imports)
