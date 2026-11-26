"""Deterministic text-sentiment lexicon. No cloud API."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z']+")

_CALM = frozenset(
    {
        "please",
        "thank",
        "thanks",
        "appreciate",
        "grateful",
    }
)
_UNCALM = frozenset(
    {
        "stupid",
        "useless",
        "idiot",
        "ridiculous",
        "hate",
        "awful",
        "terrible",
    }
)

# 1.0 is calm. Missing text is scored 0.5 by fusion, not by this function.


def sentiment_score(spoken: str) -> float:
    """Return a 0-1 calm score. Neutral text is 0.5."""
    tokens = _TOKEN.findall(spoken.casefold())
    if not tokens:
        return 0.5
    calm_hits = 0
    uncalm_hits = 0
    for index, token in enumerate(tokens):
        if token in _CALM:
            calm_hits += 1
        if token == "you" and index > 0 and tokens[index - 1] == "thank":
            continue
        if token in _UNCALM:
            uncalm_hits += 1
    raw = 0.5 + 0.2 * calm_hits - 0.25 * uncalm_hits
    return min(1.0, max(0.0, raw))
