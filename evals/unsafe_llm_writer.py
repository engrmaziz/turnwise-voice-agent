"""Test double that applies slots without validators. Not a product mode.

Imported only by ``evals.ablate_fsm``. ``tests/test_no_unsafe_writer_in_app.py``
fails if ``server/`` imports this module.
"""

from __future__ import annotations

from dialogue.slots import DialogueState, SlotValue


def apply_unchecked(state: DialogueState, slots: dict[str, str], intent: str) -> DialogueState:
    """Write slots with no ISO / roster / phone checks. Illegal on the product path."""
    merged = dict(state.slots)
    for key, value in slots.items():
        merged[key] = SlotValue(value=value, status="confirmed", source="proposal")
    return state.model_copy(update={"intent": intent, "slots": merged})
