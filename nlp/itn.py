"""Inverse text normalization. NeMo when it imports; otherwise a clinic rule set."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass

import structlog

_LOG = structlog.get_logger("nlp.itn")

_NEMO_ERROR: str | None
try:
    import nemo_text_processing  # noqa: F401

    _NEMO_ERROR = None
except Exception as exc:
    _NEMO_ERROR = type(exc).__name__

_HOUR_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
_MINUTE_WORDS = {
    "o'clock": 0,
    "oclock": 0,
    "oh clock": 0,
    "fifteen": 15,
    "thirty": 30,
    "forty five": 45,
    "forty-five": 45,
}
_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
_MONTHS = {
    "january": "January",
    "february": "February",
    "march": "March",
    "april": "April",
    "may": "May",
    "june": "June",
    "july": "July",
    "august": "August",
    "september": "September",
    "october": "October",
    "november": "November",
    "december": "December",
}
_ORDINALS = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
    "eleventh": "11",
    "twelfth": "12",
    "thirteenth": "13",
    "fourteenth": "14",
    "fifteenth": "15",
    "sixteenth": "16",
    "seventeenth": "17",
    "eighteenth": "18",
    "nineteenth": "19",
    "twentieth": "20",
    "twenty first": "21",
    "twenty-first": "21",
    "twenty second": "22",
    "twenty-second": "22",
    "twenty third": "23",
    "twenty-third": "23",
    "twenty fourth": "24",
    "twenty-fourth": "24",
    "twenty fifth": "25",
    "twenty-fifth": "25",
    "twenty sixth": "26",
    "twenty-sixth": "26",
    "twenty seventh": "27",
    "twenty-seventh": "27",
    "twenty eighth": "28",
    "twenty-eighth": "28",
    "twenty ninth": "29",
    "twenty-ninth": "29",
    "thirtieth": "30",
    "thirty first": "31",
    "thirty-first": "31",
}

Transform = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ItnResult:
    spoken: str
    normalized: str
    ok: bool
    engine: str


def nemo_import_status() -> str:
    """Exception class when NeMo is missing, or ``imported``."""
    return "imported" if _NEMO_ERROR is None else _NEMO_ERROR


def inverse_normalize_sync(spoken: str, *, transform: Transform | None = None) -> ItnResult:
    """Map spoken form to written form. ``spoken`` is never rewritten."""
    engine = "nemo" if _NEMO_ERROR is None else "rules"
    try:
        if transform is not None:
            written = transform(spoken)
        elif _NEMO_ERROR is None:
            written = _nemo(spoken)
        else:
            written = apply_rules(spoken)
    except Exception:
        _LOG.warning("itn_failed", engine=engine)
        return ItnResult(spoken=spoken, normalized=spoken, ok=False, engine=engine)
    return ItnResult(spoken=spoken, normalized=written, ok=True, engine=engine)


async def inverse_normalize(
    spoken: str,
    *,
    timeout_s: float,
    transform: Transform | None = None,
) -> ItnResult:
    """Run ITN off the loop. Timeout or exception keeps spoken and sets ok false."""
    if timeout_s <= 0:
        raise ValueError("timeout_s must be > 0")
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: inverse_normalize_sync(spoken, transform=transform)),
            timeout=timeout_s,
        )
    except TimeoutError:
        _LOG.warning("itn_timeout", timeout_s=timeout_s)
        return ItnResult(spoken=spoken, normalized=spoken, ok=False, engine="timeout")


def apply_rules(spoken: str) -> str:
    """Clock times, digit runs, and month names. Relative phrases stay."""
    return _digit_runs(_months(_clocks(spoken)))


def _clocks(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        hour = _HOUR_WORDS[match.group("hour")]
        minute_key = match.group("minute").replace("  ", " ").strip()
        minute = _MINUTE_WORDS[minute_key]
        return f"{hour}:{minute:02d}"

    pattern = (
        r"\b(?P<hour>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s+(?P<minute>o'clock|oclock|oh clock|fifteen|thirty|forty five|forty-five)\b"
    )
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _months(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        month = _MONTHS[match.group("month").lower()]
        day = match.group("day")
        if day.isdigit():
            return f"{month} {int(day)}"
        key = day.lower().replace(" ", "-")
        numeral = _ORDINALS.get(key) or _ORDINALS[day.lower()]
        return f"{month} {numeral}"

    ords = "|".join(re.escape(name) for name in sorted(_ORDINALS, key=len, reverse=True))
    months = "|".join(_MONTHS)
    pattern = rf"\b(?P<month>{months})\s+(?:the\s+)?(?P<day>\d{{1,2}}|{ords})\b"
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _digit_runs(text: str) -> str:
    words = list(_DIGIT_WORDS)
    pattern = r"\b(?:" + "|".join(words) + r")(?:\s+(?:" + "|".join(words) + r")){2,}\b"

    def repl(match: re.Match[str]) -> str:
        return "".join(_DIGIT_WORDS[part.lower()] for part in match.group(0).split())

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _nemo(spoken: str) -> str:
    from nemo_text_processing.inverse_text_normalization.inverse_normalize import (
        InverseNormalizer,
    )

    normalizer = InverseNormalizer(lang="en")
    return str(normalizer.inverse_normalize(spoken, verbose=False))
