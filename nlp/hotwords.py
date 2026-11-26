"""State-dependent hotword lists. Doctor strings come only from the roster file."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_DIGIT_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def load_roster(path: Path) -> tuple[str, ...]:
    """Read invented doctor names. Empty lines are ignored."""
    if not path.is_file():
        raise FileNotFoundError(str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    names = tuple(line.strip() for line in lines if line.strip())
    if not names:
        raise ValueError(f"doctor roster is empty: {path}")
    return names


def hotwords_for(
    vocab_id: str,
    *,
    clinic_name: str,
    doctors: Sequence[str],
) -> list[str]:
    """Build the biasing list for the expected-slot id.

    ``phone`` must not include the roster. Unknown ids fall back to greet.
    """
    if vocab_id == "doctor":
        return list(doctors)
    if vocab_id == "date":
        return [*_WEEKDAYS, *_MONTHS]
    if vocab_id == "phone":
        return list(_DIGIT_WORDS)
    return [clinic_name, *doctors]
