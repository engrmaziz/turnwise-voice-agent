"""Phrase cache: a second lookup skips the pool. Warmup misses are counted."""

from models.tts_cache import TtsCache, cached_synthesize, warmup_cache, warmup_texts
from models.tts_pool import TtsJob, TtsPool
from tests.conftest import Harness
from tests.support import counter_value


def _job(text: str, *, first_chunk: bool = True) -> TtsJob:
    return TtsJob(
        session_id="s",
        generation=0,
        text=text,
        voice="default",
        speed=1.0,
        first_chunk=first_chunk,
    )


def _counted_stub(*, frame_bytes: int) -> tuple[TtsPool, list[int]]:
    inner = TtsPool.stub(timeout_ms=800, frame_bytes=frame_bytes)
    calls = [0]
    original = inner.synth_sync

    def counted(text: str, voice: str, speed: float) -> bytes:
        calls[0] += 1
        assert original is not None
        return original(text, voice, speed)

    inner.synth_sync = counted
    return inner, calls


async def test_second_lookup_skips_the_pool(harness: Harness) -> None:
    pool, calls = _counted_stub(frame_bytes=harness.settings.tts_pcm_bytes)
    cache = TtsCache(warmup_ids=frozenset())
    job = _job("hello there")
    first = await cached_synthesize(cache, pool, job, live=lambda: 0, metrics=harness.metrics)
    second = await cached_synthesize(cache, pool, job, live=lambda: 0, metrics=harness.metrics)
    pool.close()
    assert first is not None and second is not None
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls[0] == 1
    assert counter_value(harness.metrics.tts_cache_hits) == 1.0
    assert counter_value(harness.metrics.tts_cache_misses) == 1.0


async def test_warmup_miss_increments_counter(harness: Harness) -> None:
    phrases = warmup_texts(harness.settings)
    greeting = phrases["greeting"]
    pool, _calls = _counted_stub(frame_bytes=harness.settings.tts_pcm_bytes)
    cache = TtsCache(
        warmup_ids=frozenset(harness.settings.tts_warmup_list),
        warmup_texts=frozenset(phrases.values()),
    )
    result = await cached_synthesize(
        cache,
        pool,
        _job(greeting),
        live=lambda: 0,
        metrics=harness.metrics,
        warmup_id="greeting",
    )
    pool.close()
    assert result is not None
    assert result.cache_hit is False
    assert counter_value(harness.metrics.tts_cache_miss_warmup) == 1.0


def test_warmup_fills_greeting(harness: Harness) -> None:
    pool = TtsPool.stub(timeout_ms=800, frame_bytes=harness.settings.tts_pcm_bytes)
    phrases = warmup_texts(harness.settings)
    cache = TtsCache(
        warmup_ids=frozenset(harness.settings.tts_warmup_list),
        warmup_texts=frozenset(phrases.values()),
    )
    warmup_cache(cache, pool, harness.settings, harness.metrics)
    hit = cache.lookup(phrases["greeting"], harness.settings.tts_voice, harness.settings.tts_speed)
    pool.close()
    assert hit is not None
    assert "cannot_speak" in phrases
    assert "one_moment" in phrases
