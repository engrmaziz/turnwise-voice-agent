"""Self-repair: a marker plus a later span of the same slot replaces the earlier one."""

from __future__ import annotations

from dataclasses import dataclass

from server.config import Settings

_DEFAULT_MARKERS = ("no", "sorry", "i mean", "actually")


@dataclass(frozen=True, slots=True)
class SlotSpan:
    slot: str
    start: int
    end: int
    text: str


def spans_from_bio(tokens: list[str], tags: list[str]) -> list[SlotSpan]:
    """BIO to half-open token spans. Length mismatch is a caller bug."""
    if len(tokens) != len(tags):
        raise ValueError("tokens and tags must be the same length")
    spans: list[SlotSpan] = []
    index = 0
    while index < len(tags):
        tag = tags[index]
        if tag.startswith("B-"):
            slot = tag[2:]
            end = index + 1
            while end < len(tags) and tags[end] == f"I-{slot}":
                end += 1
            spans.append(
                SlotSpan(
                    slot=slot,
                    start=index,
                    end=end,
                    text=" ".join(tokens[index:end]),
                )
            )
            index = end
            continue
        index += 1
    return spans


def apply_repairs(
    tokens: list[str],
    tags: list[str],
    settings: Settings | None = None,
) -> tuple[list[SlotSpan], int]:
    """Keep the later span of the same slot after a repair marker.

    Two markers apply left to right. A marker followed by a different slot type
    does not delete the earlier span.
    """
    markers = _markers(settings)
    spans = spans_from_bio(tokens, tags)
    if not spans:
        return [], 0
    joined = [tok.lower() for tok in tokens]
    kept = list(spans)
    repairs = 0
    for index, _token in enumerate(joined):
        window = _window_is_marker(joined, index, markers)
        if window is None:
            continue
        _start, end = window
        after = [span for span in kept if span.start >= end]
        before = [span for span in kept if span.end <= index]
        if not after or not before:
            continue
        later = after[0]
        earlier = None
        for span in reversed(before):
            if span.slot == later.slot:
                earlier = span
                break
        if earlier is None:
            continue
        kept = [span for span in kept if span is not earlier]
        repairs += 1
    return kept, repairs


def _markers(settings: Settings | None) -> tuple[str, ...]:
    if settings is None:
        return _DEFAULT_MARKERS
    parts = tuple(
        item.strip().lower() for item in settings.repair_markers.split(",") if item.strip()
    )
    return parts if parts else _DEFAULT_MARKERS


def _window_is_marker(
    tokens: list[str], index: int, markers: tuple[str, ...]
) -> tuple[int, int] | None:
    for marker in markers:
        parts = marker.split()
        if tokens[index : index + len(parts)] == parts:
            return index, index + len(parts)
    return None
