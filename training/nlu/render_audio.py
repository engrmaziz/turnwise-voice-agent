"""Mix a signal with noise at a requested SNR. Real TTS is mark bench."""

from __future__ import annotations

import argparse
import math
import random
import struct
import wave
from pathlib import Path

NOISE_LICENSE = "generated_white_noise"
MUSAN_LICENSE_MARKERS = ("creative commons", "cc-by", "cc0")


def rms(samples: list[float]) -> float:
    if not samples:
        raise ValueError("rms needs samples")
    return math.sqrt(sum(item * item for item in samples) / len(samples))


def snr_db(signal: list[float], noise: list[float]) -> float:
    """``10 * log10(signal_power / noise_power)`` after aligning lengths."""
    aligned_s, aligned_n = align_lengths(signal, noise)
    ps = rms(aligned_s) ** 2
    pn = rms(aligned_n) ** 2
    if pn <= 0.0:
        raise ValueError("noise power must be > 0")
    if ps <= 0.0:
        raise ValueError("signal power must be > 0")
    return 10.0 * math.log10(ps / pn)


def align_lengths(left: list[float], right: list[float]) -> tuple[list[float], list[float]]:
    if not left or not right:
        raise ValueError("both buffers must be non-empty")
    n = max(len(left), len(right))
    return _tile(left, n), _tile(right, n)


def mix_snr(signal: list[float], noise: list[float], snr: float) -> list[float]:
    """Scale ``noise`` so the mix has ``snr`` dB, then add."""
    aligned_s, aligned_n = align_lengths(signal, noise)
    ps = rms(aligned_s) ** 2
    pn = rms(aligned_n) ** 2
    if pn <= 0.0:
        return list(aligned_s)
    target_pn = ps / (10.0 ** (snr / 10.0))
    scale = math.sqrt(target_pn / pn)
    return [s + n * scale for s, n in zip(aligned_s, aligned_n, strict=True)]


def sine_wave(*, hz: float = 440.0, samples: int = 1600, sample_rate: int = 16000) -> list[float]:
    return [0.2 * math.sin(2.0 * math.pi * hz * i / sample_rate) for i in range(samples)]


def white_noise(*, samples: int, seed: int = 3) -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(-0.2, 0.2) for _ in range(samples)]


def musan_license_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return any(marker in text for marker in MUSAN_LICENSE_MARKERS)


def stub_tts_pcm(text: str, *, sample_rate: int = 16000) -> bytes:
    """Deterministic sine burst whose length follows the text. Not a vocoder."""
    n = max(320, min(16000, 80 * max(1, len(text.split()))))
    samples = sine_wave(samples=n, sample_rate=sample_rate)
    return _pcm16(samples)


def write_wav(path: Path, pcm: bytes, *, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)


def _tile(values: list[float], n: int) -> list[float]:
    if len(values) >= n:
        return values[:n]
    out = list(values)
    while len(out) < n:
        out.extend(values)
    return out[:n]


def _pcm16(samples: list[float]) -> bytes:
    clipped = []
    for sample in samples:
        if sample >= 1.0:
            clipped.append(32767)
        elif sample <= -1.0:
            clipped.append(-32768)
        else:
            clipped.append(int(sample * 32767.0))
    return struct.pack(f"<{len(clipped)}h", *clipped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="book tuesday at two thirty")
    parser.add_argument("--out", type=Path, default=Path("docs/results/nlu_stub.wav"))
    args = parser.parse_args(argv)
    write_wav(args.out, stub_tts_pcm(args.text))
    print(f"noise_license={NOISE_LICENSE} wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
