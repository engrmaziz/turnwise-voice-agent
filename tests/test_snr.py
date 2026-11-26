"""Requested SNR is within 1 dB of the mix."""

from training.nlu.render_audio import mix_snr, sine_wave, snr_db, white_noise


def test_mixed_snr_within_one_db() -> None:
    signal = sine_wave(samples=1600)
    noise = white_noise(samples=1600, seed=9)
    mixed = mix_snr(signal, noise, 10.0)
    noise_only = [m - s for m, s in zip(mixed, signal, strict=False)]
    # Mix may tile to the longer buffer; compare aligned mix residual.
    aligned_signal = signal[: len(mixed)]
    residual = [m - s for m, s in zip(mixed, aligned_signal, strict=True)]
    measured = snr_db(aligned_signal, residual)
    assert abs(measured - 10.0) <= 1.0
    assert noise_only  # noise contributed
