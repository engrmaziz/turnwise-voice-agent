"""Named actions. Calendar writes happen only from ``execute`` via the tool layer."""

from __future__ import annotations

from collections.abc import Callable

from dialogue.confirm import apply_no, apply_yes
from dialogue.context import StepContext
from dialogue.repair import bump_attempt, handoff_summary, template_for_attempts
from dialogue.slots import (
    DialogueState,
    SlotValue,
    merge_slots,
    missing_required,
    next_ask_slot,
    pending_values,
)

ActionFn = Callable[[DialogueState, StepContext], DialogueState]


def say_greeting(state: DialogueState, _ctx: StepContext) -> DialogueState:
    return state.model_copy(update={"last_action": "say_greeting", "last_template": "greet"})


def ask_slot(state: DialogueState, ctx: StepContext) -> DialogueState:
    merged = merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf)
    intent = ctx.intent or state.intent
    slot = next_ask_slot(intent, merged)
    if not slot:
        slot = "patient_name"
    bumped = bump_attempt(state.model_copy(update={"slots": merged, "intent": intent}), slot)
    template = template_for_attempts(bumped.attempts.get(slot, 0), ctx.settings)
    return bumped.model_copy(update={"last_action": "ask_slot", "last_template": template})


def set_patient(state: DialogueState, ctx: StepContext) -> DialogueState:
    merged = merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf)
    return state.model_copy(
        update={
            "slots": merged,
            "last_action": "set_patient",
            "last_template": "ask_intent",
        }
    )


def set_intent(state: DialogueState, ctx: StepContext) -> DialogueState:
    merged = merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf)
    return state.model_copy(
        update={
            "intent": ctx.intent or state.intent,
            "slots": merged,
            "last_action": "set_intent",
            "last_template": "ask_slot",
        }
    )


def ask_intent(state: DialogueState, _ctx: StepContext) -> DialogueState:
    bumped = bump_attempt(state, "intent")
    return bumped.model_copy(update={"last_action": "ask_intent", "last_template": "ask_intent"})


def confirm(state: DialogueState, ctx: StepContext) -> DialogueState:
    merged = merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf)
    pending = pending_values(merged)
    readback = " ".join(f"{key} {value}" for key, value in sorted(pending.items()))
    return state.model_copy(
        update={
            "slots": merged,
            "intent": ctx.intent or state.intent,
            "played_text": readback,
            "played_slots": pending,
            "last_action": "confirm",
            "last_template": "confirm_readback",
        }
    )


def execute(state: DialogueState, ctx: StepContext) -> DialogueState:
    """Mark EXECUTE. The stage calls the calendar tool; this function does not."""
    confirmed = apply_yes(state, state.played_text)
    tries = state.tool_tries
    if ctx.event == "tool_error":
        tries += 1
    return confirmed.model_copy(
        update={
            "last_action": "execute",
            "last_template": "one_moment" if tries else "execute",
            "tool_tries": tries,
        }
    )


def say_done(state: DialogueState, ctx: StepContext) -> DialogueState:
    return state.model_copy(
        update={
            "appointment_id": ctx.appointment_id or state.appointment_id,
            "last_action": "say_done",
            "last_template": "booked",
        }
    )


def reoffer(state: DialogueState, ctx: StepContext) -> DialogueState:
    slots = dict(state.slots)
    for key in ("date", "time"):
        slots.pop(key, None)
    return state.model_copy(
        update={
            "slots": slots,
            "played_text": "",
            "played_slots": {},
            "offered_version": 0,
            "offered_slot_id": "",
            "last_action": "reoffer",
            "last_template": "reoffer",
            "execute_error": ",".join(ctx.conflict_alts),
        }
    )


def handoff(state: DialogueState, _ctx: StepContext) -> DialogueState:
    return state.model_copy(
        update={
            "last_action": "handoff",
            "last_template": "handoff_summary",
            "played_text": handoff_summary(state),
        }
    )


def handoff_asr(state: DialogueState, ctx: StepContext) -> DialogueState:
    nxt = handoff(state, ctx)
    return nxt.model_copy(
        update={
            "last_action": "handoff_asr",
            "last_template": "handoff_asr",
        }
    )


def urgent_message(state: DialogueState, _ctx: StepContext) -> DialogueState:
    return state.model_copy(
        update={"last_action": "urgent_message", "last_template": "seek_emergency"}
    )


def faq_enter(state: DialogueState, ctx: StepContext) -> DialogueState:
    incoming = dict(ctx.nlu_slots)
    if "faq_query" not in incoming and ctx.spoken.strip():
        incoming["faq_query"] = ctx.spoken
    merged = merge_slots(state.slots, incoming, confidence=ctx.nlu_conf)
    return state.model_copy(
        update={
            "intent": "faq",
            "slots": merged,
            "last_action": "faq_enter",
            "last_template": "faq_search",
        }
    )


def say_faq(state: DialogueState, ctx: StepContext) -> DialogueState:
    return state.model_copy(
        update={
            "faq_chunk_id": ctx.faq_chunk_id,
            "last_action": "say_faq",
            "last_template": f"faq:{ctx.faq_chunk_id}",
            "played_text": ctx.faq_reply,
        }
    )


def say_faq_refuse(state: DialogueState, _ctx: StepContext) -> DialogueState:
    return state.model_copy(
        update={
            "faq_chunk_id": "",
            "last_action": "say_faq_refuse",
            "last_template": "faq_refuse",
            "played_text": "I do not have that in the clinic FAQ.",
        }
    )


def say_goodbye(state: DialogueState, _ctx: StepContext) -> DialogueState:
    return state.model_copy(update={"last_action": "say_goodbye", "last_template": "goodbye"})


def repair(state: DialogueState, ctx: StepContext) -> DialogueState:
    merged = merge_slots(state.slots, ctx.nlu_slots, confidence=ctx.nlu_conf)
    intent = ctx.intent or state.intent
    missing = missing_required(intent, merged)
    slot = missing[0] if missing else next_ask_slot(intent, merged) or "date"
    # Invalid values are dropped so the next ask does not replay them.
    cleaned = {key: item for key, item in merged.items() if key not in _invalid_names(merged, ctx)}
    bumped = bump_attempt(state.model_copy(update={"slots": cleaned, "intent": intent}), slot)
    template = template_for_attempts(bumped.attempts.get(slot, 0), ctx.settings)
    return bumped.model_copy(update={"last_action": "repair", "last_template": template})


def clear_pending(state: DialogueState, _ctx: StepContext) -> DialogueState:
    cleared = apply_no(state)
    return cleared.model_copy(update={"last_action": "clear_pending", "last_template": "ask_slot"})


def offer_human(state: DialogueState, _ctx: StepContext) -> DialogueState:
    """Ask whether to get a person. Does not change state_id and is not HANDOFF."""
    return state.model_copy(update={"last_action": "offer_human", "last_template": "offer_human"})


def _invalid_names(slots: dict[str, SlotValue], ctx: StepContext) -> set[str]:
    from datetime import datetime

    from dialogue.validators import invalid_slot_keys

    now = ctx.now if ctx.now is not None else datetime.now(ctx.timezone)
    return set(invalid_slot_keys(slots, roster=ctx.roster, now=now, timezone=ctx.timezone))


ACTIONS: dict[str, ActionFn] = {
    "say_greeting": say_greeting,
    "ask_slot": ask_slot,
    "set_patient": set_patient,
    "set_intent": set_intent,
    "ask_intent": ask_intent,
    "confirm": confirm,
    "execute": execute,
    "say_done": say_done,
    "reoffer": reoffer,
    "handoff": handoff,
    "handoff_asr": handoff_asr,
    "urgent_message": urgent_message,
    "faq_enter": faq_enter,
    "say_faq": say_faq,
    "say_faq_refuse": say_faq_refuse,
    "say_goodbye": say_goodbye,
    "repair": repair,
    "clear_pending": clear_pending,
    "offer_human": offer_human,
}
