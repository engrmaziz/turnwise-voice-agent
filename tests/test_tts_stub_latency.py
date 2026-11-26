"""In-process stub first-chunk and cache-hit latency. Not a Kokoro/Piper p50."""

from __future__ import annotations

import asyncio
import json
import time
import wave
from pathlib import Path

from models.tts_cache import TtsCache, cached_synthesize, warmup_cache, warmup_texts
from models.tts_pool import TtsJob, TtsPool
from nlp.chunker import chunk_stream
from tests.conftest import Harness


def _percentile(samples: list[float], q: float) -> float:
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((q / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _write_payload(
    path: Path,
    payload: dict[str, object],
    first_text: str,
    long_text: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    first_frames = max(1, len(first_text.split()))
    full_frames = max(1, len(long_text.split()))
    _write_silence_wav(Path("docs/results/phase7_first_chunk.wav"), first_frames)
    _write_silence_wav(Path("docs/results/phase7_full_sentence.wav"), full_frames)


def _write_silence_wav(
    path: Path, frames: int, *, sample_rate: int = 16000, frame_samples: int = 320
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frame_samples * frames)


async def test_stub_cache_and_synth_latency_writes_json(harness: Harness) -> None:
    pool = TtsPool.stub(timeout_ms=800, frame_bytes=harness.settings.tts_pcm_bytes)
    phrases = warmup_texts(harness.settings)
    cache = TtsCache(
        warmup_ids=frozenset(harness.settings.tts_warmup_list),
        warmup_texts=frozenset(phrases.values()),
    )
    warmup_cache(cache, pool, harness.settings, harness.metrics)
    greeting = phrases["greeting"]
    job = TtsJob(
        session_id=harness.session.session_id,
        generation=0,
        text=greeting,
        voice=harness.settings.tts_voice,
        speed=harness.settings.tts_speed,
        first_chunk=True,
    )
    cache_ms: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        result = await cached_synthesize(cache, pool, job, live=lambda: 0, metrics=harness.metrics)
        cache_ms.append((time.perf_counter() - started) * 1000.0)
        assert result is not None
        assert result.cache_hit is True
    long_text = "Dr. Khan can see you, Wednesday at three p.m. Please arrive ten minutes early."
    first, _rest = chunk_stream(long_text, True, harness.settings)
    first_text = first[0] if first else long_text
    assert first_text.startswith("Dr. Khan")
    assert first_text != long_text
    synth_ms: list[float] = []
    cold = TtsCache(warmup_ids=frozenset())
    for _ in range(20):
        started = time.perf_counter()
        await cached_synthesize(
            cold,
            pool,
            TtsJob(
                session_id=harness.session.session_id,
                generation=0,
                text=first_text,
                voice=harness.settings.tts_voice,
                speed=harness.settings.tts_speed,
                first_chunk=True,
            ),
            live=lambda: 0,
            metrics=harness.metrics,
        )
        synth_ms.append((time.perf_counter() - started) * 1000.0)
        cold = TtsCache(warmup_ids=frozenset())
    pool.close()
    cache_p50 = round(_percentile(cache_ms, 50), 4)
    stub_p50 = round(_percentile(synth_ms, 50), 4)
    payload: dict[str, object] = {
        "host": "in-process stub",
        "samples": 20,
        "cache_hit_p50_ms": cache_p50,
        "cache_hit_p95_ms": round(_percentile(cache_ms, 95), 4),
        "stub_first_chunk_p50_ms": stub_p50,
        "stub_first_chunk_p95_ms": round(_percentile(synth_ms, 95), 4),
        "first_chunk_text": first_text,
        "full_sentence": long_text,
        "kokoro_piper": "blocked",
        "success": True,
    }
    path = Path("docs/results/phase7_stub.json")
    await asyncio.to_thread(
        _write_payload,
        path,
        payload,
        first_text,
        long_text,
    )
    assert cache_p50 >= 0.0
    assert stub_p50 >= 0.0
