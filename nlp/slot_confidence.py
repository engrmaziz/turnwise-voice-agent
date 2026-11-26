"""Min word confidence over a character span. Missing scores fail closed at 0.0."""

from __future__ import annotations

from collections.abc import Sequence

from models.asr_types import WordConf


def slot_confidence(words: Sequence[WordConf], start_char: int, end_char: int) -> float:
    """Minimum confidence of words whose text overlaps ``[start_char, end_char)``.

    Character offsets are against the spoken string built by joining word
    texts with a single space. An empty span, a span that covers no word, or
    a covered word with ``confidence is None`` yields 0.0 so confirmation
    later fails closed.
    """
    if end_char <= start_char:
        return 0.0
    cursor = 0
    scores: list[float] = []
    for index, word in enumerate(words):
        if index > 0:
            cursor += 1
        begin = cursor
        finish = cursor + len(word.text)
        cursor = finish
        if finish <= start_char or begin >= end_char:
            continue
        if word.confidence is None:
            return 0.0
        scores.append(word.confidence)
    if not scores:
        return 0.0
    return min(scores)
