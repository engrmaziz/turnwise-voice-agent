"""Synthetic cancel latency: barge_in return to last outbound PCM write."""

from __future__ import annotations

import asyncio
import contextlib
import time

from pipeline.session import Session

TARGET_MS = 100.0


class StubPcmSender:
    """In-process outbound writer. Cancellation is the thing under test."""

    def __init__(self, *, frame_s: float = 0.005) -> None:
        if frame_s <= 0:
            raise ValueError("frame_s must be > 0")
        self.frame_s = frame_s
        self.last_write = 0.0
        self.writes = 0

    async def run(self) -> None:
        try:
            while True:
                self.last_write = time.perf_counter()
                self.writes += 1
                await asyncio.sleep(self.frame_s)
        except asyncio.CancelledError:
            raise


async def measure_cancel_latency_ms(session: Session, *, frame_s: float = 0.005) -> float:
    """Return milliseconds using appendix E: last write minus barge_in return.

    If the last write landed before ``barge_in`` returned, no extra frame leaked
    and the number is the time until the speaking task actually stopped.
    """
    sender = StubPcmSender(frame_s=frame_s)
    task = asyncio.create_task(sender.run(), name="stub-pcm")
    session.track_speaking(task)
    await asyncio.sleep(frame_s * 4)
    session.barge_in()
    t_return = time.perf_counter()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    t_done = time.perf_counter()
    last = sender.last_write
    latency_s = last - t_return if last >= t_return else max(0.0, t_done - t_return)
    return latency_s * 1000.0
