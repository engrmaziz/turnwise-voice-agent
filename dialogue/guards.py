"""Named guards. Unknown names fail at table load, not via eval."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from dialogue.context import StepContext
from dialogue.repair import template_for_attempts
from dialogue.slots import DialogueState, SlotValue, has_identity, merge_slots, missing_required
from dialogue.validators import invalid_slot_keys, validate_slot
from nlp.nlu_vocab import INTENTS
from nlp.urgent import keyword_list, spoken_has_urgent
from server.config import Settings

GuardFn = Callable[[DialogueState, StepContext], bool]

BOOKING_INTENTS = frozenset({"book", "reschedule", "cancel", "check_appointment"})


def guard_none(_state: DialogueState, _ctx: StepContext) -> bool:
    return True


def guard_kw(_state: DialogueState, ctx: StepContext) -> bool:
    return spoken_has_urgent(ctx.spoken, keyword_list(ctx.settings))


def guard_valid_identity(state: DialogueState, ctx: StepContext) -> bool:
    merged = _merged(state, ctx)
    if not has_identity(merged):
        return False
    return _all_valid(merged, ctx, keys=("patient_name", "phone", "dob"))


def guard_repair_handoff(state: DialogueState, ctx: StepContext) -> bool:
    if guard_valid_identity(state, ctx):
        return False
    peak = max(state.attempts.values(), default=0)
    return peak >= ctx.settings.repair_handoff_after


def guard_known_intent(_state: DialogueState, ctx: StepContext) -> bool:
    return ctx.intent in BOOKING_INTENTS


def guard_faq_intent(_state: DialogueState, ctx: StepContext) -> bool:
    return ctx.intent == "faq"


def guard_schema_missing(state: DialogueState, ctx: StepContext) -> bool:
    merged = _merged(state, ctx)
    intent = ctx.intent or state.intent
    if _invalid_keys(merged, ctx):
        return False
    return bool(missing_required(intent, merged))


def guard_schema_complete(state: DialogueState, ctx: StepContext) -> bool:
    merged = _merged(state, ctx)
    intent = ctx.intent or state.intent
    if missing_required(intent, merged):
        return False
    return not _invalid_keys(merged, ctx)


def guard_slot_invalid(state: DialogueState, ctx: StepContext) -> bool:
    merged = _merged(state, ctx)
    return bool(_invalid_keys(merged, ctx))


def guard_bind_played(state: DialogueState, ctx: StepContext) -> bool:
    del ctx
    if not state.played_text.strip():
        return False
    return bool(state.played_slots)


def guard_faq_hit(_state: DialogueState, ctx: StepContext) -> bool:
    return bool(ctx.faq_chunk_id)


def guard_offer_latched(_state: DialogueState, ctx: StepContext) -> bool:
    return ctx.offer_latched


def guard_retry_exhausted(state: DialogueState, ctx: StepContext) -> bool:
    return state.tool_tries >= ctx.settings.tool_retry_limit


def _merged(state: DialogueState, ctx: StepContext) -> dict[str, SlotValue]:
    return merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf, source="nlu")


def _invalid_keys(slots: dict[str, SlotValue], ctx: StepContext) -> list[str]:
    now = ctx.now if ctx.now is not None else datetime.now(ctx.timezone)
    return invalid_slot_keys(slots, roster=ctx.roster, now=now, timezone=ctx.timezone)


def _all_valid(slots: dict[str, SlotValue], ctx: StepContext, *, keys: tuple[str, ...]) -> bool:
    now = ctx.now if ctx.now is not None else datetime.now(ctx.timezone)
    for key in keys:
        item = slots.get(key)
        if item is None:
            continue
        if validate_slot(key, item.value, roster=ctx.roster, now=now, timezone=ctx.timezone):
            return False
    return True


def known_intent_name(name: str) -> bool:
    return name in INTENTS


def repair_template(state: DialogueState, slot: str, settings: Settings) -> str:
    return template_for_attempts(state.attempts.get(slot, 0), settings)


GUARDS: dict[str, GuardFn] = {
    "none": guard_none,
    "kw": guard_kw,
    "valid_identity": guard_valid_identity,
    "repair_handoff": guard_repair_handoff,
    "known_intent": guard_known_intent,
    "faq_intent": guard_faq_intent,
    "schema_missing": guard_schema_missing,
    "schema_complete": guard_schema_complete,
    "slot_invalid": guard_slot_invalid,
    "bind_played": guard_bind_played,
    "faq_hit": guard_faq_hit,
    "offer_latched": guard_offer_latched,
    "retry_exhausted": guard_retry_exhausted,
}
