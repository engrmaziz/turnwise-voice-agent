"""Slot schema per intent. Status is pending until a yes binds played text."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SlotStatus = Literal["pending", "confirmed"]
SlotSource = Literal["nlu", "proposal", "tool"]

CRITICAL_SLOTS = frozenset(
    {
        "patient_name",
        "dob",
        "phone",
        "date",
        "time",
        "doctor",
        "appointment_id",
    }
)

BOOK_REQUIRED = frozenset({"patient_name", "phone", "doctor", "date", "time"})
IDENTITY_PHONE = frozenset({"patient_name", "phone"})
IDENTITY_DOB = frozenset({"patient_name", "dob"})


class SlotValue(BaseModel):
    """One slot the FSM believes. Raw ASR doctor strings are never stored."""

    model_config = ConfigDict(frozen=True)

    value: str
    confidence: float = 1.0
    status: SlotStatus = "pending"
    source: SlotSource = "nlu"


class DialogueState(BaseModel):
    """Dialogue belief. The FSM is the only writer."""

    model_config = ConfigDict(frozen=True)

    state_id: str = "GREET"
    intent: str | None = None
    slots: dict[str, SlotValue] = Field(default_factory=dict)
    attempts: dict[str, int] = Field(default_factory=dict)
    played_text: str = ""
    played_slots: dict[str, str] = Field(default_factory=dict)
    last_action: str = ""
    last_template: str = ""
    last_guard: str = ""
    faq_chunk_id: str = ""
    appointment_id: str = ""
    offered_slot_id: str = ""
    offered_version: int = 0
    tool_tries: int = 0
    execute_error: str = ""
    say_filler: int = 0


def filled_names(slots: dict[str, SlotValue]) -> set[str]:
    return {key for key, item in slots.items() if item.value.strip()}


def required_for_intent(intent: str | None, slots: dict[str, SlotValue]) -> frozenset[str]:
    """Required keys given what is already present (cancel/check alternatives)."""
    if intent == "book":
        return BOOK_REQUIRED
    if intent == "reschedule":
        names = filled_names(slots)
        if "appointment_id" in names:
            return frozenset({"appointment_id", "date", "time"})
        return frozenset({"patient_name", "phone", "date", "time"})
    if intent == "cancel":
        names = filled_names(slots)
        if "appointment_id" in names:
            return frozenset({"appointment_id"})
        return frozenset({"patient_name", "phone", "date"})
    if intent == "check_appointment":
        names = filled_names(slots)
        if "appointment_id" in names:
            return frozenset({"appointment_id"})
        return frozenset({"patient_name", "phone"})
    return frozenset()


def missing_required(intent: str | None, slots: dict[str, SlotValue]) -> list[str]:
    required = required_for_intent(intent, slots)
    have = filled_names(slots)
    return sorted(key for key in required if key not in have)


def has_identity(slots: dict[str, SlotValue]) -> bool:
    have = filled_names(slots)
    return have >= IDENTITY_PHONE or have >= IDENTITY_DOB


def next_ask_slot(intent: str | None, slots: dict[str, SlotValue]) -> str:
    missing = missing_required(intent, slots)
    if missing:
        return missing[0]
    if not has_identity(slots) and "patient_name" not in filled_names(slots):
        return "patient_name"
    if not has_identity(slots):
        return "phone"
    return ""


def merge_slots(
    current: dict[str, SlotValue],
    incoming: dict[str, str],
    *,
    confidence: dict[str, float] | None = None,
    source: SlotSource = "nlu",
) -> dict[str, SlotValue]:
    """Overlay incoming values as pending. Confirmed slots are not overwritten."""
    out = dict(current)
    conf = confidence or {}
    for key, value in incoming.items():
        stripped = value.strip()
        if not stripped:
            continue
        existing = out.get(key)
        if existing is not None and existing.status == "confirmed":
            continue
        out[key] = SlotValue(
            value=stripped,
            confidence=conf.get(key, 1.0),
            status="pending",
            source=source,
        )
    return out


def confirmed_only(slots: dict[str, SlotValue]) -> dict[str, str]:
    return {key: item.value for key, item in slots.items() if item.status == "confirmed"}


def pending_values(slots: dict[str, SlotValue]) -> dict[str, str]:
    return {key: item.value for key, item in slots.items() if item.status == "pending"}
