"""TTS-down plays the cached cannot_speak phrase, or ends the session if the cache is empty."""

from models.tts_cache import TtsCache
from models.tts_pool import TtsPool
from pipeline.event import EventKind
from pipeline.stages.audio_out import AudioOutHandler
from server.playback import PlaybackCursor
from tests.conftest import Harness
from tests.support import counter_value


async def test_cached_cannot_speak_plays(harness: Harness) -> None:
    sent: list[bytes] = []

    async def send(data: bytes) -> None:
        sent.append(data)

    phrase = "I am having trouble speaking. Please hold."
    cache = TtsCache(warmup_ids=frozenset({"cannot_speak"}), warmup_texts=frozenset({phrase}))
    cache.store(
        phrase,
        harness.settings.tts_voice,
        harness.settings.tts_speed,
        b"\x00" * harness.settings.tts_pcm_bytes,
        warmup=True,
    )
    pool = TtsPool.unavailable(timeout_ms=50)
    handler = AudioOutHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        pool=pool,
        cache=cache,
        playback=PlaybackCursor(),
        send=send,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {"text": "long content", "voice": "default", "speed": 1.0, "filler": 0, "first_chunk": 1},
    )
    await handler(event)
    assert sent
    assert handler.closed is False


async def test_empty_cache_closes_session(harness: Harness) -> None:
    sent: list[bytes] = []

    async def send(data: bytes) -> None:
        sent.append(data)

    handler = AudioOutHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        pool=TtsPool.unavailable(timeout_ms=50),
        cache=TtsCache(warmup_ids=frozenset()),
        playback=PlaybackCursor(),
        send=send,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {"text": "hello there", "voice": "default", "speed": 1.0, "filler": 0, "first_chunk": 1},
    )
    await handler(event)
    assert sent == []
    assert handler.closed is True
    assert harness.session.tts_dead is True
    await handler(event)
    assert sent == []
    assert counter_value(harness.metrics.degraded, rung="tts") >= 1.0
