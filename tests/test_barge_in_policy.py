"""On barge-in, store the acked prefix and cancel tracked speaking tasks."""

import asyncio
import contextlib

import pytest

from pipeline.event import EventKind
from pipeline.stages.barge import BargeHandler
from server.playback import PlaybackCursor
from tests.conftest import Harness
from tests.support import counter_value


async def test_played_text_is_acked_prefix_and_tts_cancels(harness: Harness) -> None:
    cancelled = asyncio.Event()

    async def speak() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(speak())
    await asyncio.sleep(0)
    harness.session.track_speaking(task)
    playback = PlaybackCursor()
    playback.note_chunk(0, 9, "ABCDEFGHIJ")
    playback.ack(3)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=playback,
    )
    handler.note_partial("wait stop")
    handler.note_speech_ms(300.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=4)
    assert await handler.consider(event, should_barge=True) is True
    assert harness.session.played_text == "ABCD"
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled() or cancelled.is_set()
    assert counter_value(harness.metrics.barge_in) == 1.0


async def test_missing_map_stores_empty_played_text(harness: Harness) -> None:
    async def speak() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(speak())
    harness.session.track_speaking(task)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    handler.note_partial("stop")
    handler.note_speech_ms(300.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    assert await handler.consider(event, should_barge=True) is True
    assert harness.session.played_text == ""
    assert counter_value(harness.metrics.playback_unmap) == 1.0
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
