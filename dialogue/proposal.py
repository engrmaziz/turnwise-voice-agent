"""LLM proposals go through the same validators as NLU. Does not open SQLite."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dialogue.slots import DialogueState, merge_slots
from dialogue.validators import (
    validate_date,
    validate_dob,
    validate_doctor,
    validate_phone,
    validate_time,
)
from models.llm_client import ProposalSchema
from nlp.nlu_vocab import INTENTS


class ProposalRejected(ValueError):
    """Proposal failed the closed schema or a slot validator."""


def parse_proposal(payload: dict[str, object]) -> ProposalSchema:
    extra = set(payload) - {"intent", "slots"}
    if extra:
        raise ProposalRejected(f"extra field {sorted(extra)[0]}")
    parsed = ProposalSchema.model_validate(payload)
    if parsed.intent not in INTENTS:
        raise ProposalRejected("unknown intent")
    return parsed


def apply_proposal(
    state: DialogueState,
    proposal: ProposalSchema,
    *,
    roster: tuple[str, ...],
    now: datetime,
    timezone: ZoneInfo,
) -> DialogueState:
    """Return the same state object when validation fails. Does not open SQLite."""
    today = now.astimezone(timezone).date()
    for key, value in proposal.slots.items():
        if _slot_error(key, value, roster=roster, today=today) is not None:
            return state
    merged = merge_slots(state.slots, proposal.slots, source="proposal")
    return state.model_copy(update={"intent": proposal.intent, "slots": merged})


def _slot_error(
    key: str,
    value: str,
    *,
    roster: tuple[str, ...],
    today: object,
) -> str | None:
    from datetime import date as date_cls

    day = today if isinstance(today, date_cls) else None
    if day is None:
        return "clock missing"
    if key == "date":
        return validate_date(value, today=day)
    if key == "time":
        return validate_time(value)
    if key == "phone":
        return validate_phone(value)
    if key == "doctor":
        return validate_doctor(value, roster)
    if key == "dob":
        return validate_dob(value, today=day)
    if value.casefold() in {"tomorrow", "today", "next tuesday"}:
        return "relative date is not ISO"
    return None
