"""Two-turn latch offers a human. Offer is not HANDOFF. Keywords still win."""

from dialogue.actions import offer_human
from dialogue.context import StepContext
from dialogue.frustration import FrustrationLatch
from dialogue.planner import select_template_text
from dialogue.slots import DialogueState
from pipeline.event import EventKind
from pipeline.stages.tts_norm import TtsNormHandler
from server.config import Settings
from tests.conftest import Harness
from tests.fsm_helpers import DOCTOR, identity_slots, make_machine
from tests.test_urgent_keyword import (
    test_chest_pain_from_greet_is_urgent,
    test_nlu_book_cannot_veto_keyword,
)


def test_one_turn_does_not_offer() -> None:
    settings = Settings()
    latch = FrustrationLatch()
    assert latch.note(0.9, settings) is False
    assert latch.offer_human is False


def test_two_consecutive_turns_offer() -> None:
    settings = Settings()
    latch = FrustrationLatch()
    latch.note(0.9, settings)
    assert latch.note(0.9, settings) is True
    assert latch.take_offer_say() is True
    assert latch.take_offer_say() is False


def test_below_threshold_resets_the_count() -> None:
    settings = Settings()
    latch = FrustrationLatch()
    latch.note(0.9, settings)
    latch.note(0.1, settings)
    assert latch.offer_human is False
    latch.note(0.9, settings)
    assert latch.offer_human is False


def test_offer_is_not_handoff() -> None:
    machine = make_machine()
    machine.start()
    machine.nlu(
        spoken="Jordan Pike 5550101234",
        intent="out_of_scope",
        slots=identity_slots(),
    )
    machine.nlu(spoken="book with Avery", intent="book", slots={"doctor": DOCTOR})
    state = offer_human(machine.state, StepContext(event="offer_human"))
    assert state.state_id != "HANDOFF"
    assert state.last_template == "offer_human"
    machine.state = state
    machine.nlu(
        spoken="yes",
        intent="yes",
        slots={},
        offer_latched=True,
    )
    assert machine.state.state_id == "HANDOFF"


def test_keyword_plus_high_score_is_still_urgent() -> None:
    machine = make_machine()
    machine.start()
    machine.state = machine.state.model_copy(
        update={"last_action": "offer_human", "last_template": "offer_human"}
    )
    machine.nlu(
        spoken="I have chest pain",
        intent="book",
        slots={},
        offer_latched=True,
    )
    assert machine.state.state_id == "URGENT"
    assert machine.state.last_template == "seek_emergency"


def test_short_templates_for_ask_and_confirm() -> None:
    state = DialogueState(intent="book", last_action="ask_slot", last_template="ask_slot")
    _, text = select_template_text("ask_slot", state, short=True)
    assert text == "What next?"
    confirm = DialogueState(intent="book", last_action="confirm", last_template="confirm_readback")
    _, confirm_text = select_template_text("confirm", confirm, short=True)
    assert confirm_text == "Is that right?"


async def test_frustrated_speed_when_offer_latched(harness: Harness) -> None:
    harness.session.offer_human = True
    captured: list[float] = []

    async def forward(event: object) -> None:
        payload = getattr(event, "payload", {})
        captured.append(float(payload.get("speed") or 0.0))

    handler = TtsNormHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        forward=forward,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {"text": "Would you like me to get a person?", "filler": 0, "first_chunk": 1},
    )
    await handler(event)
    assert captured == [harness.settings.tts_frustrated_speed]


def test_keyword_path_still_imported_with_emotion_unloaded() -> None:
    test_chest_pain_from_greet_is_urgent()
    test_nlu_book_cannot_veto_keyword()
