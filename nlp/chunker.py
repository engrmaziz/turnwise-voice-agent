"""Abbreviation-safe streaming chunker. First clause flushes without a period."""

from __future__ import annotations

import re

from server.config import Settings

_TOKEN = re.compile(r"\S+")


def chunk_stream(buffer: str, first_chunk: bool, settings: Settings) -> tuple[list[str], str]:
    """Return flushed clauses and the unflushed remainder.

    Sentence end always flushes. A comma flushes when the clause meets the
    word minimum. Abbreviations in ``tts_abbrev`` are not split points.
    """
    stripped = buffer.strip()
    if not stripped:
        return [], ""
    tokens = list(_TOKEN.finditer(stripped))
    if not tokens:
        return [], buffer
    min_words = settings.tts_first_chunk_min_words if first_chunk else settings.tts_later_min_words
    abbrev = settings.tts_abbrev_set
    split_at = -1
    for index, match in enumerate(tokens):
        word_count = index + 1
        token = match.group(0)
        if _is_abbrev(token, abbrev):
            # Mid-utterance "Dr." / "p.m." is not a split. A SAY that ends on
            # an abbreviation still has to flush as a completed sentence.
            if index == len(tokens) - 1:
                split_at = match.end()
                break
            continue
        boundary = _sentence_end(token, abbrev) or token.endswith(",")
        if not boundary:
            continue
        if word_count >= min_words:
            split_at = match.end()
            break
        if _sentence_end(token, abbrev):
            split_at = match.end()
            break
    if split_at < 0:
        return [], buffer
    head = stripped[:split_at].strip()
    tail = stripped[split_at:].strip()
    if not head:
        return [], buffer
    return [head], tail if tail else ""


def hold_prefix(buffer: str) -> tuple[str, str]:
    """Flush a whole-word prefix. A single long token still flushes."""
    stripped = buffer.strip()
    if not stripped:
        return "", buffer
    tokens = list(_TOKEN.finditer(stripped))
    if not tokens:
        return stripped, ""
    if len(tokens) == 1:
        return stripped, ""
    last = tokens[-1]
    # Keep the last token if it looks incomplete (no trailing punct, buffer
    # ended mid-word). Hold still must not wait forever on one token.
    head = stripped[: last.end()].strip()
    return head, ""


def _is_abbrev(token: str, abbrev: frozenset[str]) -> bool:
    folded = token.casefold()
    if folded in abbrev:
        return True
    if not folded.endswith("."):
        return False
    return folded in abbrev or folded.rstrip(".") + "." in abbrev


def _sentence_end(token: str, abbrev: frozenset[str]) -> bool:
    if token.endswith(("!", "?")):
        return True
    if not token.endswith("."):
        return False
    return not _is_abbrev(token, abbrev)
