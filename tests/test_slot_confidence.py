"""Min word confidence over a character span. Missing scores are 0.0."""

from models.asr_types import WordConf
from nlp.slot_confidence import slot_confidence


def test_min_of_covered_words() -> None:
    words = (
        WordConf(text="book", start_ms=0, end_ms=200, confidence=0.9),
        WordConf(text="tuesday", start_ms=200, end_ms=500, confidence=0.4),
    )
    spoken = "book tuesday"
    start = spoken.index("tuesday")
    assert slot_confidence(words, start, start + len("tuesday")) == 0.4
    assert slot_confidence(words, 0, len(spoken)) == 0.4


def test_empty_span_is_zero() -> None:
    words = (WordConf(text="book", start_ms=0, end_ms=100, confidence=0.9),)
    assert slot_confidence(words, 0, 0) == 0.0
    assert slot_confidence((), 0, 4) == 0.0


def test_missing_confidence_is_zero() -> None:
    words = (
        WordConf(text="book", start_ms=0, end_ms=100, confidence=None),
        WordConf(text="now", start_ms=100, end_ms=200, confidence=0.8),
    )
    assert slot_confidence(words, 0, 4) == 0.0
