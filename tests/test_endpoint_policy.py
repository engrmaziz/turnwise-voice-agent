"""Locked order of should_end_turn, including digit patience before p_complete."""

from models.onnx_pool import TurnScorer
from pipeline.event import Event, EventKind
from pipeline.stages.endpoint import EndpointHandler, should_end_turn
from server.config import Settings
from tests.conftest import Harness


def test_non_digit_hard_ceiling_does_not_cut_a_phone_slot() -> None:
    """The 1200 ms ceiling used to run before digit patience. That was the bug."""
    settings = Settings()
    assert not should_end_turn(1200.0, "five five five one two", 0.0, "phone", settings)


def test_empty_text_never_ends() -> None:
    settings = Settings()
    assert not should_end_turn(5000.0, "  ", 1.0, "none", settings)
    assert not should_end_turn(5000.0, "", 1.0, "phone", settings)


def test_digit_patience_beats_high_p_complete() -> None:
    """Digit patience runs before p_complete so a high score cannot cut a phone."""
    settings = Settings()
    assert not should_end_turn(300.0, "five", 0.99, "phone", settings)
    assert not should_end_turn(700.0, "five five five", 0.99, "phone", settings)
    assert not should_end_turn(700.0, "march third nineteen ninety", 0.99, "dob", settings)


def test_phone_700ms_holds_open_question_800ms_ends() -> None:
    settings = Settings()
    assert not should_end_turn(700.0, "five five five", 0.0, "phone", settings)
    assert should_end_turn(800.0, "what time do you open", 0.0, "none", settings)


def test_digit_hard_ceiling_at_2000() -> None:
    settings = Settings()
    assert not should_end_turn(1999.0, "five five five", 0.0, "phone", settings)
    assert should_end_turn(2000.0, "five five five", 0.0, "phone", settings)


def test_non_digit_hard_ceiling() -> None:
    settings = Settings()
    assert should_end_turn(1200.0, "book tuesday", 0.0, "none", settings)


def test_high_p_complete_after_200ms_on_open_slot() -> None:
    settings = Settings()
    assert not should_end_turn(199.0, "book tuesday", 0.99, "none", settings)
    assert should_end_turn(200.0, "book tuesday", 0.99, "none", settings)


def test_mid_p_complete_after_500ms() -> None:
    settings = Settings()
    assert not should_end_turn(499.0, "book tuesday", 0.5, "none", settings)
    assert should_end_turn(500.0, "book tuesday", 0.5, "none", settings)


def test_default_800ms_when_p_complete_is_zero() -> None:
    settings = Settings()
    assert not should_end_turn(799.0, "book tuesday", 0.0, "none", settings)
    assert should_end_turn(800.0, "book tuesday", 0.0, "none", settings)


def test_digit_skips_default_800_after_patience() -> None:
    settings = Settings()
    assert not should_end_turn(1300.0, "five five five", 0.0, "phone", settings)


def test_session_expected_slot_default_is_none(harness: Harness) -> None:
    assert harness.session.expected_slot == "none"
    harness.session.expected_slot = "phone"
    assert harness.session.expected_slot == "phone"
    settings = Settings()
    assert not should_end_turn(800.0, "five", 0.0, harness.session.expected_slot, settings)


async def test_turn_end_latches_until_next_speech(harness: Harness) -> None:
    emitted: list[EventKind] = []

    async def forward(event: Event) -> None:
        emitted.append(event.kind)

    handler = EndpointHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        scorer=TurnScorer.unavailable(timeout_ms=20),
        forward=forward,
    )
    handler.note_text("book tuesday")
    first = await handler.evaluate_silence(800.0)
    second = await handler.evaluate_silence(900.0)
    assert first is not None
    assert first.kind is EventKind.TURN_END
    assert second is None
    assert handler.turn_ends == 1
    assert emitted == [EventKind.TURN_END]
    handler.note_speech()
    handler.note_text("book tuesday")
    third = await handler.evaluate_silence(800.0)
    assert third is not None
    assert handler.turn_ends == 2


async def test_timeout_zeroes_p_complete_and_silence_still_ends(harness: Harness) -> None:
    settings = harness.settings.model_copy(
        update={"turn_model_enabled": True, "turn_timeout_ms": 20}
    )
    handler = EndpointHandler(
        session=harness.session,
        settings=settings,
        metrics=harness.metrics,
        scorer=TurnScorer.stub(timeout_ms=20, score=0.99, sleep_s=0.2),
    )
    handler.note_text("book tuesday")
    ended = await handler.evaluate_silence(800.0)
    assert ended is not None
    from tests.support import counter_value

    assert counter_value(harness.metrics.turn_model_timeouts) == 1.0
