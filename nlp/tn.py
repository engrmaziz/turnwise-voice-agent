"""Deterministic TTS normalization. Inverse of ITN; no LLM."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_PHONE = re.compile(r"\b(\d{7,10})\b")
_TITLE = re.compile(r"\bDr\.?(?=\s|,|$)", re.IGNORECASE)

_ONES = (
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
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty")
_MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_ORDINALS = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
    11: "eleventh",
    12: "twelfth",
    13: "thirteenth",
    14: "fourteenth",
    15: "fifteenth",
    16: "sixteenth",
    17: "seventeenth",
    18: "eighteenth",
    19: "nineteenth",
    20: "twentieth",
    21: "twenty-first",
    22: "twenty-second",
    23: "twenty-third",
    24: "twenty-fourth",
    25: "twenty-fifth",
    26: "twenty-sixth",
    27: "twenty-seventh",
    28: "twenty-eighth",
    29: "twenty-ninth",
    30: "thirtieth",
    31: "thirty-first",
}
_LETTERS = {
    "a": "ay",
    "b": "bee",
    "c": "see",
    "d": "dee",
    "e": "ee",
    "f": "eff",
    "g": "jee",
    "h": "aych",
    "i": "eye",
    "j": "jay",
    "k": "kay",
    "l": "ell",
    "m": "em",
    "n": "en",
    "o": "oh",
    "p": "pee",
    "q": "cue",
    "r": "ar",
    "s": "ess",
    "t": "tee",
    "u": "you",
    "v": "vee",
    "w": "double-you",
    "x": "ex",
    "y": "why",
    "z": "zee",
}


class TnContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    spell_name: bool = False
    digit_mode: bool = False
    confirm: bool = False


def normalize_for_tts(text: str, context: TnContext) -> str:
    """Written-to-spoken mapping. Unknown name characters become ``symbol``."""
    spoken, _unknown = normalize_counted(text, context)
    return spoken


def normalize_counted(text: str, context: TnContext) -> tuple[str, int]:
    unknown = 0
    out = _TIME.sub(_time_repl, text)
    out = _ISO_DATE.sub(_date_repl, out)
    out = _PHONE.sub(_phone_repl, out)
    out = _TITLE.sub("Doctor", out)
    if context.spell_name:
        out, unknown = _spell_names(out)
    if context.confirm:
        out = _confirm_break(out)
    return re.sub(r"\s+", " ", out).strip(), unknown


def _time_repl(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = "a.m." if hour < 12 else "p.m."
    hour12 = hour % 12
    if hour12 == 0:
        hour12 = 12
    hour_word = _ONES[hour12]
    if minute == 0:
        return f"{hour_word} {meridiem}"
    if minute < 20:
        return f"{hour_word} {_ONES[minute]} {meridiem}"
    tens, ones = divmod(minute, 10)
    minute_word = _TENS[tens] if ones == 0 else f"{_TENS[tens]} {_ONES[ones]}"
    return f"{hour_word} {minute_word} {meridiem}"


def _date_repl(match: re.Match[str]) -> str:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    if month < 1 or month > 12 or day < 1 or day > 31:
        return match.group(0)
    month_word = _MONTHS[month]
    day_word = _ORDINALS.get(day, str(day))
    year_word = _year_words(year)
    return f"{month_word} {day_word}, {year_word}"


def _year_words(year: int) -> str:
    thousands, rest = divmod(year, 1000)
    hundreds, tail = divmod(rest, 100)
    parts: list[str] = []
    if thousands:
        parts.append(f"{_ONES[thousands]} thousand")
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if tail == 0:
        return " ".join(parts) if parts else _ONES[0]
    if tail < 20:
        parts.append(_ONES[tail])
        return " ".join(parts)
    tens, ones = divmod(tail, 10)
    tens_word = _TENS[tens] if tens < len(_TENS) else str(tens * 10)
    if ones:
        parts.append(f"{tens_word} {_ONES[ones]}")
    else:
        parts.append(tens_word)
    return " ".join(parts)


def _phone_repl(match: re.Match[str]) -> str:
    digits = match.group(1)
    return " ".join(_ONES[int(ch)] for ch in digits)


def _spell_names(text: str) -> tuple[str, int]:
    unknown = 0
    parts: list[str] = []
    for char in text:
        lower = char.casefold()
        if lower in _LETTERS:
            parts.append(_LETTERS[lower])
        elif char.isspace() or char in {",", ".", "?", "!"} or char.isalnum():
            parts.append(char)
        else:
            parts.append("symbol")
            unknown += 1
    return re.sub(r" +", " ", " ".join(parts)).strip(), unknown


def _confirm_break(text: str) -> str:
    if "," in text:
        return text
    match = re.search(r"\.\s+", text)
    if match is not None:
        return text[: match.start()] + ", " + text[match.end() :]
    words = text.split()
    if len(words) <= 3:
        return text
    return " ".join(words[:3]) + ", " + " ".join(words[3:])
