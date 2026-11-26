"""TTS pool drops stale generations, times out, and rejects empty PCM."""

import asyncio

import pytest

from models.tts_pool import TtsError, TtsJob, TtsPool, TtsTimeoutError
from tests.conftest import Harness


def _job(harness: Harness, *, generation: int | None = None) -> TtsJob:
    return TtsJob(
        session_id=harness.session.session_id,
        generation=harness.session.generation if generation is None else generation,
        text="hello there",
        voice="default",
        speed=1.0,
        first_chunk=True,
    )


async def test_result_dropped_after_barge_in(harness: Harness) -> None:
    pool = TtsPool.stub(
        timeout_ms=800,
        frame_bytes=harness.settings.tts_pcm_bytes,
        sleep_s=0.08,
    )
    task = asyncio.create_task(
        pool.synthesize(_job(harness), live=lambda: harness.session.generation)
    )
    await asyncio.sleep(0.01)
    harness.session.barge_in()
    result = await task
    pool.close()
    assert result is None


async def test_timeout_raises_typed_error(harness: Harness) -> None:
    pool = TtsPool.stub(
        timeout_ms=50,
        frame_bytes=harness.settings.tts_pcm_bytes,
        sleep_s=1.0,
    )
    with pytest.raises(TtsTimeoutError):
        await pool.synthesize(_job(harness), live=lambda: harness.session.generation)
    pool.close()


async def test_empty_pcm_is_an_error(harness: Harness) -> None:
    pool = TtsPool.stub(
        timeout_ms=800,
        frame_bytes=harness.settings.tts_pcm_bytes,
        pcm=b"",
    )
    with pytest.raises(TtsError, match="empty pcm"):
        await pool.synthesize(_job(harness), live=lambda: harness.session.generation)
    pool.close()
