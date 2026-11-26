"""TTS render, speaking-rate stretch, and SNR mix. Reuses the NLU mix helper."""

from __future__ import annotations

from training.nlu.render_audio import mix_snr, sine_wave, white_noise

MATRIX_RATES = (0.9, 1.1)


def stretch(samples: list[float], rate: float) -> list[float]:
    """Nearest-neighbour resample. Rate 0.9 lengthens, 1.1 shortens."""
    if rate <= 0:
        raise ValueError("rate must be > 0")
    if not samples:
        raise ValueError("samples must be non-empty")
    n = max(1, round(len(samples) / rate))
    return [samples[min(len(samples) - 1, int(index * rate))] for index in range(n)]


def render_utterance(
    *,
    rate: float,
    snr_db: float | None,
    seed: int = 1,
    samples: int = 1600,
) -> list[float]:
    """Stub renderer: a sine, optionally stretched and mixed. Not a spoken model."""
    signal = sine_wave(samples=samples)
    stretched = stretch(signal, rate)
    if snr_db is None:
        return stretched
    noise = white_noise(samples=len(stretched), seed=seed)
    return mix_snr(stretched, noise, snr_db)
