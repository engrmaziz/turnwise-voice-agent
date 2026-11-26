"""Explicit confirm for critical slots. Yes does not bind empty playback."""

from dialogue.confirm import apply_no, apply_yes, needs_explicit_confirm
from dialogue.slots import DialogueState, SlotValue
from server.config import Settings
from tests.fsm_helpers import make_machine


def test_critical_slot_under_threshold_is_explicit() -> None:
    settings = Settings()
    assert needs_explicit_confirm("phone", 0.5, settings) is True
    assert needs_explicit_confirm("reason", 0.5, settings) is False
    assert needs_explicit_confirm("phone", 0.9, settings) is False


def test_yes_with_empty_played_text_leaves_pending() -> None:
    state = DialogueState(
        state_id="CONFIRM",
        slots={"phone": SlotValue(value="5550101234", status="pending")},
        played_text="",
        played_slots={"phone": "5550101234"},
    )
    nxt = apply_yes(state, "")
    assert nxt is state
    assert nxt.slots["phone"].status == "pending"


def test_yes_binds_played_value_not_pending_if_they_differ() -> None:
    state = DialogueState(
        state_id="CONFIRM",
        slots={"phone": SlotValue(value="5550100000", status="pending")},
        played_text="phone 5550101234",
        played_slots={"phone": "5550101234"},
    )
    nxt = apply_yes(state, state.played_text)
    assert nxt.slots["phone"].status == "confirmed"
    assert nxt.slots["phone"].value == "5550101234"


def test_implicit_confirm_does_not_mark_confirmed_immediately() -> None:
    machine = make_machine()
    machine.start()
    machine.nlu(
        spoken="Jordan Pike 5550101234",
        intent="out_of_scope",
        slots={"patient_name": "Jordan Pike", "phone": "5550101234"},
    )
    phone = machine.state.slots.get("phone")
    assert phone is not None
    assert phone.status == "pending"


def test_no_clears_pending_and_increments_attempts() -> None:
    state = DialogueState(
        state_id="CONFIRM",
        slots={
            "phone": SlotValue(value="5550101234", status="pending"),
            "patient_name": SlotValue(value="Jordan Pike", status="confirmed"),
        },
        played_text="phone 5550101234",
        played_slots={"phone": "5550101234"},
    )
    nxt = apply_no(state)
    assert "phone" not in nxt.slots
    assert nxt.slots["patient_name"].status == "confirmed"
    assert nxt.attempts["phone"] == 1
    assert nxt.played_text == ""
