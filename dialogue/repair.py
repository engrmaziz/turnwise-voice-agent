"""Attempt counters. Attempt 2 spells or digits; attempt 3 hands off."""

from __future__ import annotations

from dialogue.slots import DialogueState, confirmed_only
from server.config import Settings

SPELL_TEMPLATE = "spell_or_digits"
HANDOFF_TEMPLATE = "handoff_summary"


def template_for_attempts(attempts: int, settings: Settings) -> str:
    if attempts >= settings.repair_handoff_after:
        return HANDOFF_TEMPLATE
    if attempts >= settings.repair_modality_after:
        return SPELL_TEMPLATE
    return "ask_slot"


def handoff_summary(state: DialogueState) -> str:
    """Confirmed slots only. Pending values are omitted."""
    confirmed = confirmed_only(state.slots)
    if not confirmed:
        return "handoff with no confirmed slots"
    parts = [f"{key} {value}" for key, value in sorted(confirmed.items())]
    return "handoff " + ", ".join(parts)


def bump_attempt(state: DialogueState, slot: str) -> DialogueState:
    attempts = dict(state.attempts)
    attempts[slot] = attempts.get(slot, 0) + 1
    return state.model_copy(update={"attempts": attempts})
