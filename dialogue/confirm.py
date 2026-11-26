"""Explicit versus implicit confirm. Yes binds played_text, not a silent pending value."""

from __future__ import annotations

from dialogue.slots import CRITICAL_SLOTS, DialogueState, SlotValue
from server.config import Settings


def needs_explicit_confirm(slot: str, confidence: float, settings: Settings) -> bool:
    """Critical slots under confirm_explicit_below are explicit. ``reason`` is not."""
    if slot not in CRITICAL_SLOTS:
        return False
    return confidence < settings.confirm_explicit_below


def apply_yes(state: DialogueState, played_text: str) -> DialogueState:
    """Confirm using the values that were played. Empty playback leaves pending."""
    if not played_text.strip():
        return state
    played = dict(state.played_slots)
    if not played:
        return state
    slots = dict(state.slots)
    for key, value in played.items():
        previous = slots.get(key)
        confidence = previous.confidence if previous is not None else 1.0
        source = previous.source if previous is not None else "nlu"
        slots[key] = SlotValue(
            value=value,
            confidence=confidence,
            status="confirmed",
            source=source,
        )
    return state.model_copy(update={"slots": slots, "played_text": played_text})


def apply_no(state: DialogueState) -> DialogueState:
    """Clear pending slots and increment attempts. Confirmed slots stay."""
    slots = {key: item for key, item in state.slots.items() if item.status == "confirmed"}
    attempts = dict(state.attempts)
    for key, item in state.slots.items():
        if item.status == "pending":
            attempts[key] = attempts.get(key, 0) + 1
    return state.model_copy(
        update={
            "slots": slots,
            "attempts": attempts,
            "played_text": "",
            "played_slots": {},
        }
    )
