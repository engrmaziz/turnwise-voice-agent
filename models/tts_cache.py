"""In-memory phrase cache. Warmup runs at process start, not per call."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from dialogue.templates import load_templates
from models.tts_pool import TtsError, TtsJob, TtsPool, TtsResult
from pipeline.metrics import StageMetrics
from server.config import Settings

Synth = Callable[[TtsJob], bytes]


def cache_key(text: str, voice: str, speed: float) -> str:
    blob = f"{text}|{voice}|{speed:.2f}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TtsCache:
    """Process-local PCM keyed by sha256(text|voice|speed)."""

    def __init__(
        self,
        *,
        warmup_ids: frozenset[str],
        warmup_texts: frozenset[str] = frozenset(),
    ) -> None:
        self._pcm: dict[str, bytes] = {}
        self._warmup_ids = warmup_ids
        self._warmup_texts = warmup_texts
        self._warmup_keys: set[str] = set()

    def lookup(self, text: str, voice: str, speed: float) -> bytes | None:
        return self._pcm.get(cache_key(text, voice, speed))

    def store(
        self, text: str, voice: str, speed: float, pcm: bytes, *, warmup: bool = False
    ) -> str:
        key = cache_key(text, voice, speed)
        self._pcm[key] = pcm
        if warmup:
            self._warmup_keys.add(key)
        return key

    def is_warmup(self, *, phrase_id: str = "", text: str = "") -> bool:
        if phrase_id and phrase_id in self._warmup_ids:
            return True
        return bool(text and text in self._warmup_texts)


def warmup_texts(settings: Settings) -> dict[str, str]:
    catalog = load_templates()
    out: dict[str, str] = {}
    for phrase_id in settings.tts_warmup_list:
        text = catalog.warmup.get(phrase_id, "")
        if text:
            out[phrase_id] = text
    return out


def warmup_cache(
    cache: TtsCache,
    pool: TtsPool,
    settings: Settings,
    metrics: StageMetrics,
) -> None:
    """Fill greeting and filler phrases. Failures leave a hole counted at runtime."""
    del metrics
    if not pool.available or pool.synth_sync is None:
        return
    voice = settings.tts_voice
    speed = settings.tts_speed
    for _phrase_id, text in warmup_texts(settings).items():
        try:
            pcm = pool.synth_sync(text, voice, speed)
        except TtsError:
            continue
        if not pcm:
            continue
        cache.store(text, voice, speed, pcm, warmup=True)


async def cached_synthesize(
    cache: TtsCache,
    pool: TtsPool,
    job: TtsJob,
    *,
    live: Callable[[], int],
    metrics: StageMetrics,
    warmup_id: str = "",
) -> TtsResult | None:
    started = time.perf_counter()
    hit = cache.lookup(job.text, job.voice, job.speed)
    if hit is not None:
        if live() != job.generation:
            return None
        metrics.tts_cache_hits.inc()
        latency_ms = (time.perf_counter() - started) * 1000.0
        if job.first_chunk:
            metrics.tts_first_chunk.observe(latency_ms / 1000.0)
        return TtsResult(pcm=hit, generation=job.generation, cache_hit=True, latency_ms=latency_ms)
    metrics.tts_cache_misses.inc()
    if cache.is_warmup(phrase_id=warmup_id, text=job.text):
        metrics.tts_cache_miss_warmup.inc()
    result = await pool.synthesize(job, live=live)
    if result is None:
        return None
    cache.store(job.text, job.voice, job.speed, result.pcm)
    latency_ms = (time.perf_counter() - started) * 1000.0
    if job.first_chunk:
        metrics.tts_first_chunk.observe(latency_ms / 1000.0)
    return TtsResult(
        pcm=result.pcm,
        generation=result.generation,
        cache_hit=False,
        latency_ms=latency_ms,
    )
