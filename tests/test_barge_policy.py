"""Barge-in gates: AEC, 250 ms of speech, and a non-backchannel partial."""

import asyncio
import contextlib

from nlp.backchannel import is_backchannel
from pipeline.event import EventKind
from pipeline.stages.barge import BargeHandler
from tests.conftest import Harness
from tests.support import counter_value


def test_default_backchannel_list_excludes_yes(harness: Harness) -> None:
    phrases = harness.settings.backchannel_list
    assert "yes" not in phrases
    assert "okay" in phrases


def test_okay_is_backchannel_off_confirm_and_answer_on_confirm(harness: Harness) -> None:
    phrases = harness.settings.backchannel_list
    assert is_backchannel(
        "okay",
        expected_slot="none",
        duration_ms=200.0,
        phrases=phrases,
        max_ms=harness.settings.backchannel_max_ms,
    )
    assert not is_backchannel(
        "okay",
        expected_slot="confirm",
        duration_ms=200.0,
        phrases=phrases,
        max_ms=harness.settings.backchannel_max_ms,
    )


def test_duration_gate_and_yes_no_slot(harness: Harness) -> None:
    phrases = harness.settings.backchannel_list
    assert not is_backchannel(
        "yeah",
        expected_slot="none",
        duration_ms=400.0,
        phrases=phrases,
        max_ms=harness.settings.backchannel_max_ms,
    )
    assert not is_backchannel(
        "yeah",
        expected_slot="confirm",
        duration_ms=100.0,
        phrases=phrases,
        max_ms=harness.settings.backchannel_max_ms,
    )


async def _speaking(harness: Harness) -> asyncio.Task[None]:
    async def hold() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(hold())
    harness.session.track_speaking(task)
    return task


async def test_100ms_does_not_fire_250ms_does(harness: Harness) -> None:
    from server.playback import PlaybackCursor

    speaking = await _speaking(harness)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    handler.note_partial("I need to stop")
    handler.note_speech_ms(100.0)
    assert await handler.consider(event, should_barge=True) is False
    assert handler.hits == 0
    handler.note_speech_ms(250.0)
    assert await handler.consider(event, should_barge=True) is True
    assert handler.hits == 1
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking


async def test_aec_false_does_not_fire(harness: Harness) -> None:
    from server.playback import PlaybackCursor

    speaking = await _speaking(harness)
    harness.session.barge_in_enabled = False
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    handler.note_partial("stop please")
    handler.note_speech_ms(300.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    assert await handler.consider(event, should_barge=True) is False
    assert handler.hits == 0
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking


async def test_backchannel_does_not_increment_barge_in(harness: Harness) -> None:
    from server.playback import PlaybackCursor

    speaking = await _speaking(harness)
    before = counter_value(harness.metrics.barge_in)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    handler.note_partial("okay")
    handler.note_speech_ms(200.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    assert await handler.consider(event, should_barge=False) is False
    assert counter_value(harness.metrics.barge_in) == before
    assert counter_value(harness.metrics.backchannel_ignored) == 1.0
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking
