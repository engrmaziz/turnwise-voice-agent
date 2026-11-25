"""Dead-mic and clipping detectors. Thresholds come from the caller."""

from __future__ import annotations

import struct
from collections import deque


def unpack_pcm16(pcm: bytes) -> tuple[int, ...]:
    if len(pcm) % 2 != 0:
        raise ValueError("pcm16 byte length must be even")
    count = len(pcm) // 2
    if count == 0:
        return ()
    return struct.unpack(f"<{count}h", pcm)


def rms_full_scale(pcm: bytes) -> float:
    """RMS of int16 samples divided by 32768. Uses integer squares."""
    samples = unpack_pcm16(pcm)
    if not samples:
        return 0.0
    acc = 0
    for sample in samples:
        acc += sample * sample
    mean = acc / len(samples)
    return float((mean**0.5) / 32768.0)


def clip_fraction(pcm: bytes, peak: int) -> float:
    samples = unpack_pcm16(pcm)
    if not samples:
        return 0.0
    clipped = 0
    for sample in samples:
        if sample >= peak or sample <= -peak:
            clipped += 1
    return clipped / len(samples)


class QualityWindow:
    """Sliding RMS flags. Duration is inferred from frame count times frame_ms."""

    __slots__ = ("_clip_peak", "_frame_ms", "_frames", "_max_frames")

    def __init__(self, *, frame_ms: int, window_s: float, clip_peak: int) -> None:
        if frame_ms < 1:
            raise ValueError("frame_ms must be >= 1")
        if window_s <= 0:
            raise ValueError("window_s must be > 0")
        self._frame_ms = frame_ms
        self._max_frames = max(1, round(window_s * 1000 / frame_ms))
        self._clip_peak = clip_peak
        self._frames: deque[tuple[float, float]] = deque(maxlen=self._max_frames)

    def push(self, pcm: bytes) -> None:
        self._frames.append((rms_full_scale(pcm), clip_fraction(pcm, self._clip_peak)))

    def silent(self, rms_threshold: float) -> bool:
        if len(self._frames) < self._max_frames:
            return False
        return all(rms <= rms_threshold for rms, _clip in self._frames)

    def clipped(self, fraction_threshold: float) -> bool:
        if not self._frames:
            return False
        total = 0.0
        for _rms, clip in self._frames:
            total += clip
        return (total / len(self._frames)) >= fraction_threshold

    @property
    def filled(self) -> bool:
        return len(self._frames) >= self._max_frames
