"""Pre-roll ring keeps 500 ms plus the triggering frame."""

import asyncio
import contextlib
import math
import struct

from models.vad_pool import VadPool
from pipeline.audio.preroll import Preroll
from pipeline.event import EventKind
from pipeline.stages.vad import VadHandler
from server.config import Settings
from tests.conftest import Harness


def _frame(fill: int) -> bytes:
    return bytes([fill, 0]) * 320


def test_snapshot_is_preroll_plus_trigger() -> None:
    settings = Settings()
    ring = Preroll(settings.vad_preroll_frames)
    for i in range(settings.vad_preroll_frames):
        ring.push(_frame(i % 250))
    trigger = _frame(255)
    snap = ring.snapshot(trigger)
    expected = settings.vad_preroll_frames * 640 + 640
    assert len(snap) == expected
    assert snap.endswith(trigger)


def test_underrun_at_100ms() -> None:
    settings = Settings()
    ring = Preroll(settings.vad_preroll_frames)
    frames_100ms = 100 // settings.ws_frame_ms
    for _ in range(frames_100ms):
        ring.push(_frame(1))
    snap = ring.snapshot(_frame(2))
    expected_full = settings.vad_preroll_frames * 640 + 640
    assert len(snap) < expected_full
    assert len(snap) == (frames_100ms + 1) * 640


def _sine_frame(samples: int = 320) -> bytes:
    out = [int(32767 * 0.2 * math.sin(2.0 * math.pi * 440.0 * i / 16000)) for i in range(samples)]
    return struct.pack(f"<{samples}h", *out)


async def test_preroll_survives_barge_in(harness: Harness) -> None:
    async def speak() -> None:
        await asyncio.sleep(60)

    speaking = asyncio.create_task(speak())
    harness.session.track_speaking(speaking)
    handler = VadHandler(
        session=harness.session,
        settings=harness.settings,
        engine=VadPool.unavailable(timeout_ms=30),
        metrics=harness.metrics,
    )
    pcm = _sine_frame()
    started_at: int | None = None
    for index in range(20):
        harness.session.put_pcm(index, pcm)
        await handler(
            harness.session.create_event(EventKind.AUDIO, {"samples": 320}, frame_index=index)
        )
        if handler.speech_starts:
            started_at = index
            break
    speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await speaking
    assert started_at is not None
    stored = harness.session.get_pcm(started_at)
    assert stored is not None
    assert len(stored) > 640
    assert harness.session.generation == 1
