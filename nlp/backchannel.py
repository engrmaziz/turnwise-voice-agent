"""State-dependent backchannel filter. ``yes`` is never in the default list."""

from __future__ import annotations

from collections.abc import Sequence

_YES_NO_SLOTS = frozenset({"confirm", "yes_no"})


def is_backchannel(
    text: str,
    *,
    expected_slot: str,
    duration_ms: float,
    phrases: Sequence[str],
    max_ms: float,
) -> bool:
    """True only for short continuer phrases outside a yes/no slot.

    Duration under ``max_ms`` is required. ``okay`` on ``confirm`` is an answer.
    """
    if expected_slot in _YES_NO_SLOTS:
        return False
    if duration_ms >= max_ms:
        return False
    stripped = " ".join(text.lower().split()).strip(" .,!?")
    allowed = {item.strip().lower() for item in phrases if item.strip()}
    return stripped in allowed
