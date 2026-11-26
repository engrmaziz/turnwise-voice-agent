"""TTFA histograms observe on play-ack. Filler and content are different samples."""

import asyncio
import time

from models.tts_cache import TtsCache
from models.tts_pool import TtsPool
from pipeline.event import EventKind
from pipeline.stages.audio_out import AudioOutHandler
from server.playback import PlaybackCursor
from tests.conftest import Harness
from tests.support import counter_value, histogram_count, histogram_sum


async def _play(
    harness: Harness,
    handler: AudioOutHandler,
    *,
    text: str,
    filler: int,
) -> None:
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {
            "text": text,
            "voice": "default",
            "speed": 1.0,
            "filler": filler,
            "first_chunk": 1 if filler == 1 or handler.emitted == 0 else 0,
        },
    )
    await handler(event)


def _handler(harness: Harness, pool: TtsPool, playback: PlaybackCursor) -> AudioOutHandler:
    return AudioOutHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        pool=pool,
        cache=TtsCache(warmup_ids=frozenset()),
        playback=playback,
        send=None,
    )


async def test_filler_then_content_two_samples(harness: Harness) -> None:
    pool = TtsPool.stub(timeout_ms=800, frame_bytes=harness.settings.tts_pcm_bytes)
    playback = PlaybackCursor()
    handler = _handler(harness, pool, playback)
    harness.session.turn_end_ts = time.monotonic()
    await _play(harness, handler, text="One moment.", filler=1)
    content_index = handler.emitted
    handler.note_play_ack(0)
    await asyncio.sleep(0.02)
    await _play(harness, handler, text="Your visit is booked.", filler=0)
    handler.note_play_ack(content_index)
    pool.close()
    assert histogram_count(harness.metrics.ttfa) == 1.0
    assert histogram_count(harness.metrics.ttfa_content) == 1.0
    assert histogram_sum(harness.metrics.ttfa) != histogram_sum(harness.metrics.ttfa_content)
    assert counter_value(harness.metrics.playback_unmap) == 0.0


async def test_content_only_equal_samples(harness: Harness) -> None:
    pool = TtsPool.stub(timeout_ms=800, frame_bytes=harness.settings.tts_pcm_bytes)
    playback = PlaybackCursor()
    handler = _handler(harness, pool, playback)
    harness.session.turn_end_ts = time.monotonic()
    await _play(harness, handler, text="Hello, this is Turnwise Clinic.", filler=0)
    handler.note_play_ack(0)
    pool.close()
    assert histogram_count(harness.metrics.ttfa) == 1.0
    assert histogram_count(harness.metrics.ttfa_content) == 1.0
    assert histogram_sum(harness.metrics.ttfa) == histogram_sum(harness.metrics.ttfa_content)
    assert histogram_count(harness.metrics.ttfa) > 0.0
    assert counter_value(harness.metrics.playback_unmap) == 0.0
    assert playback.prefix_for_ack(0)
