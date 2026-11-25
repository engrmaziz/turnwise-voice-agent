"""Ingress: resample once, store PCM on the session, forward AUDIO to VAD."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from pipeline.audio.format import resample_mono_pcm16
from pipeline.event import Event, EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from pipeline.stage import Stage

Forward = Callable[[Event], Awaitable[None]]


class AudioInHandler:
    """Resamples wire PCM onto the 16 kHz bus and counts live frames."""

    __slots__ = (
        "_dst_hz",
        "_forward",
        "_metrics",
        "_session",
        "_src_hz",
        "frames_accepted",
    )

    def __init__(
        self,
        *,
        session: Session | None = None,
        src_hz: int = 16000,
        dst_hz: int = 16000,
        metrics: StageMetrics | None = None,
        forward: Forward | None = None,
    ) -> None:
        self._session = session
        self._src_hz = src_hz
        self._dst_hz = dst_hz
        self._metrics = metrics
        self._forward = forward
        self.frames_accepted = 0

    async def __call__(self, event: Event) -> None:
        if event.kind is not EventKind.AUDIO or event.frame_index is None:
            return
        session = self._session
        if session is not None:
            raw = session.take_wire_pcm(event.frame_index)
            if raw is None:
                return
            started = time.perf_counter()
            pcm = resample_mono_pcm16(raw, self._src_hz, self._dst_hz)
            if self._metrics is not None:
                self._metrics.resample.observe(time.perf_counter() - started)
            if len(pcm) != 640:
                # One 20 ms frame at 16 kHz is 320 samples. Leftover bytes are
                # a rate/frame mismatch; drop rather than emit a short block.
                return
            session.put_pcm(event.frame_index, pcm)
        self.frames_accepted += 1
        if self._forward is not None:
            await self._forward(event)


def forward_to(stage: Stage) -> Forward:
    return stage.emit
