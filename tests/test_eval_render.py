"""Rate stretch and SNR mix. Disfluency inserts a T5.5.1 marker."""

from evals.disfluency_inject import inject_disfluency
from evals.render import MATRIX_RATES, render_utterance, stretch
from server.config import Settings
from training.nlu.render_audio import sine_wave, snr_db


def test_matrix_rates_and_stretch() -> None:
    assert MATRIX_RATES == (0.9, 1.1)
    signal = sine_wave(samples=100)
    slow = stretch(signal, 0.9)
    fast = stretch(signal, 1.1)
    assert len(slow) > len(signal)
    assert len(fast) < len(signal)


def test_snr_none_is_clean() -> None:
    clean = render_utterance(rate=1.0, snr_db=None, samples=800)
    noisy = render_utterance(rate=1.0, snr_db=10.0, samples=800)
    residual = [m - s for m, s in zip(noisy, clean, strict=False)]
    aligned = clean[: len(noisy)]
    measured = snr_db(aligned, residual[: len(aligned)])
    assert abs(measured - 10.0) <= 1.0


def test_disfluency_inserts_marker() -> None:
    settings = Settings()
    plain = inject_disfluency("book Tuesday", enabled=False, settings=settings)
    assert plain == "book Tuesday"
    marked = inject_disfluency("book Tuesday", enabled=True, settings=settings)
    assert "no" in marked
    assert marked != plain
