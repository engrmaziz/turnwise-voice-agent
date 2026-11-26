"""Attempt 2 spells or digits. Attempt 3 hands off with confirmed slots only."""

from dialogue.repair import HANDOFF_TEMPLATE, SPELL_TEMPLATE, handoff_summary, template_for_attempts
from dialogue.slots import DialogueState, SlotValue
from server.config import Settings


def test_attempt_two_selects_spell_or_digits() -> None:
    settings = Settings()
    assert template_for_attempts(2, settings) == SPELL_TEMPLATE
    assert template_for_attempts(3, settings) == HANDOFF_TEMPLATE


def test_handoff_summary_uses_confirmed_only() -> None:
    state = DialogueState(
        slots={
            "phone": SlotValue(value="5550101234", status="confirmed"),
            "date": SlotValue(value="2026-12-15", status="pending"),
        }
    )
    summary = handoff_summary(state)
    assert "5550101234" in summary
    assert "2026-12-15" not in summary
