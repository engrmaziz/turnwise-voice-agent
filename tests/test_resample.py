"""Linear resample of mono PCM16. Peak frequency stays near 440 Hz."""

from __future__ import annotations

import cmath
import math
import struct
import time

import pytest

from pipeline.audio.format import resample_mono_pcm16


def _sine(hz: float, rate: int, seconds: float, amp: float = 0.2) -> bytes:
    n = int(rate * seconds)
    samples = [int(32767 * amp * math.sin(2.0 * math.pi * hz * i / rate)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


def _peak_hz(pcm: bytes, rate: int) -> float:
    n = len(pcm) // 2
    samples = struct.unpack(f"<{n}h", pcm)
    lo = max(1, int(200 * n / rate))
    hi = min(n // 2 - 1, int(800 * n / rate))
    best_k = lo
    best_mag = 0.0
    for k in range(lo, hi + 1):
        acc = 0j
        omega = -2j * math.pi * k / n
        for i, sample in enumerate(samples):
            acc += sample * cmath.exp(omega * i)
        mag = abs(acc)
        if mag > best_mag:
            best_mag = mag
            best_k = k
    return best_k * rate / n


def test_odd_byte_length_raises() -> None:
    with pytest.raises(ValueError, match="even"):
        resample_mono_pcm16(b"\x00", 16000, 16000)


def test_identity_16k() -> None:
    pcm = _sine(440, 16000, 0.05)
    assert resample_mono_pcm16(pcm, 16000, 16000) == pcm


def test_8k_and_48k_sine_peak_within_one_bin() -> None:
    for src in (8000, 48000):
        pcm = _sine(440, src, 0.25)
        out = resample_mono_pcm16(pcm, src, 16000)
        assert len(out) % 2 == 0
        peak = _peak_hz(out, 16000)
        bin_hz = 16000 / (len(out) // 2)
        assert abs(peak - 440.0) <= bin_hz + 1e-6


def test_resample_p50_logged() -> None:
    pcm = _sine(440, 48000, 0.02)
    times: list[float] = []
    for _ in range(30):
        started = time.perf_counter()
        resample_mono_pcm16(pcm, 48000, 16000)
        times.append((time.perf_counter() - started) * 1000.0)
    measured = sorted(times[5:])
    p50 = measured[len(measured) // 2]
    assert p50 < 50.0
    test_resample_p50_logged.p50_ms = p50  # type: ignore[attr-defined]
