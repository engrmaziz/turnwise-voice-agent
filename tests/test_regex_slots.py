"""Deterministic matcher exists for ablation and is unused by the app."""

from pathlib import Path

from dialogue.regex_slots import match_slots
from nlp.hotwords import load_roster


def test_matcher_finds_roster_doctor() -> None:
    roster = load_roster(Path("data/doctors.txt"))
    slots = match_slots("book with Dr. Avery Lang on Tuesday 5550101234", roster)
    assert slots["doctor"] == "Dr. Avery Lang"
    assert slots["date"] == "tuesday"
    assert slots["phone"] == "5550101234"
