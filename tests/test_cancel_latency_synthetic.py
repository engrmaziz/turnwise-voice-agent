"""Synthetic cancel latency TARGET 100 ms, plus labeled false/missed counters."""

import asyncio
import contextlib
import logging

from evals.turn.latency import TARGET_MS, measure_cancel_latency_ms
from pipeline.event import EventKind
from pipeline.metrics import observe_response_gap
from pipeline.stages.barge import BargeHandler
from server.playback import PlaybackCursor
from tests.conftest import Harness
from tests.support import counter_value, histogram_count

_LOG = logging.getLogger("turnwise.tests.cancel")


async def test_stub_cancel_latency_under_100ms(harness: Harness) -> None:
    latency_ms = await measure_cancel_latency_ms(harness.session)
    harness.metrics.cancel_latency.observe(latency_ms / 1000.0)
    _LOG.info("cancel_latency_ms=%.4f", latency_ms)
    print(f"cancel_latency_ms={latency_ms:.4f}")
    assert latency_ms <= TARGET_MS


async def test_backchannel_does_not_increment_false_barge_in(harness: Harness) -> None:
    async def hold() -> None:
        await asyncio.sleep(60)

    speaking = asyncio.create_task(hold())
    harness.session.track_speaking(speaking)
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
    assert counter_value(harness.metrics.false_barge_in) == 0.0
    assert counter_value(harness.metrics.backchannel_ignored) == 1.0
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking


async def test_300ms_non_backchannel_is_a_hit(harness: Harness) -> None:
    async def hold() -> None:
        await asyncio.sleep(60)

    speaking = asyncio.create_task(hold())
    harness.session.track_speaking(speaking)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    handler.note_partial("I need to cancel")
    handler.note_speech_ms(300.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    assert await handler.consider(event, should_barge=True) is True
    assert handler.hits == 1
    assert counter_value(harness.metrics.barge_in) == 1.0
    assert counter_value(harness.metrics.false_barge_in) == 0.0
    assert counter_value(harness.metrics.missed_barge_in) == 0.0
    with contextlib.suppress(asyncio.CancelledError):
        await speaking


async def test_ignored_burst_increments_missed_only_when_labeled(harness: Harness) -> None:
    async def hold() -> None:
        await asyncio.sleep(60)

    speaking = asyncio.create_task(hold())
    harness.session.track_speaking(speaking)
    handler = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    handler.note_partial("stop")
    handler.note_speech_ms(100.0)
    event = harness.session.create_event(EventKind.AUDIO, frame_index=0)
    assert await handler.consider(event, should_barge=True) is False
    assert counter_value(harness.metrics.missed_barge_in) == 1.0
    unlabeled = BargeHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        playback=PlaybackCursor(),
    )
    unlabeled.note_partial("stop")
    unlabeled.note_speech_ms(100.0)
    assert await unlabeled.consider(event, should_barge=None) is False
    assert counter_value(harness.metrics.missed_barge_in) == 1.0
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking


def test_response_gap_and_early_cutoff_collectors_exist(harness: Harness) -> None:
    observe_response_gap(harness.metrics, 1.0, 1.25)
    harness.metrics.early_cutoff.inc()
    assert histogram_count(harness.metrics.response_gap) == 1.0
    assert counter_value(harness.metrics.early_cutoff) == 1.0
