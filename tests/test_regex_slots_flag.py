"""The week-6 matcher stays off the default import path."""

from pathlib import Path

from server.config import Settings


def test_regex_slots_enabled_defaults_false() -> None:
    assert Settings().regex_slots_enabled is False


def test_app_does_not_import_regex_slots() -> None:
    text = Path("server/app.py").read_text(encoding="utf-8")
    assert "regex_slots" not in text


def test_dialogue_stage_imports_matcher_only_behind_the_flag() -> None:
    text = Path("pipeline/stages/dialogue.py").read_text(encoding="utf-8")
    assert "from dialogue.regex_slots import match_slots" in text
    flag_line = next(
        line for line in text.splitlines() if "regex_slots_enabled" in line and "if " in line
    )
    assert "regex_slots_enabled" in flag_line
