"""Deterministic urgent-keyword matcher. A hit is sufficient to escalate."""

from __future__ import annotations

from nlp.disfluency import apply_repairs
from nlp.nlu_features import tokenize
from server.config import Settings

DEFAULT_KEYWORDS = (
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "cant breathe",
    "shortness of breath",
    "passing out",
    "fainted",
    "stroke",
    "suicidal",
)


def keyword_list(settings: Settings | None = None) -> tuple[str, ...]:
    if settings is None:
        return DEFAULT_KEYWORDS
    parts = tuple(item.strip() for item in settings.urgent_keywords.split(",") if item.strip())
    return parts if parts else DEFAULT_KEYWORDS


def spoken_has_urgent(text: str, keywords: tuple[str, ...] | None = None) -> bool:
    """Casefold substring match on disfluency-repaired spoken text.

    Negation and past tense are not stripped. ``chest`` alone does not match.
    """
    needles = keywords if keywords is not None else DEFAULT_KEYWORDS
    repaired = _repaired_text(text)
    folded = repaired.casefold()
    for keyword in needles:
        needle = keyword.casefold().strip()
        if needle and needle in folded:
            return True
    return False


def _repaired_text(text: str) -> str:
    tokens = tokenize(text)
    if not tokens:
        return text
    tags = ["O"] * len(tokens)
    spans, _n = apply_repairs(tokens, tags, None)
    if not spans:
        return " ".join(tokens)
    return " ".join(tokens)
