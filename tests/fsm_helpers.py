"""Shared FSM fixtures for phase 6 tests."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dialogue.machine import DialogueMachine
from nlp.hotwords import load_roster
from server.config import Settings

DOCTOR = "Dr. Avery Lang"
PHONE = "5550101234"
NAME = "Jordan Pike"
DATE = "2026-12-15"
TIME = "15:00"
TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 26, 9, 0, tzinfo=TZ)


def make_machine(settings: Settings | None = None) -> DialogueMachine:
    roster = load_roster(Path("data/doctors.txt"))
    return DialogueMachine(
        settings=settings if settings is not None else Settings(),
        roster=roster,
        timezone=TZ,
        now=NOW,
    )


def identity_slots() -> dict[str, str]:
    return {"patient_name": NAME, "phone": PHONE}


def book_slots() -> dict[str, str]:
    return {
        "patient_name": NAME,
        "phone": PHONE,
        "doctor": DOCTOR,
        "date": DATE,
        "time": TIME,
    }
