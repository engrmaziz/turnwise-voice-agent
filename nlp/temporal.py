"""Deterministic relative-date resolution against the session clock."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty-first": 21,
    "twenty first": 21,
    "twenty-second": 22,
    "twenty second": 22,
    "twenty-third": 23,
    "twenty third": 23,
    "twenty-fourth": 24,
    "twenty fourth": 24,
    "twenty-fifth": 25,
    "twenty fifth": 25,
    "twenty-sixth": 26,
    "twenty sixth": 26,
    "twenty-seventh": 27,
    "twenty seventh": 27,
    "twenty-eighth": 28,
    "twenty eighth": 28,
    "twenty-ninth": 29,
    "twenty ninth": 29,
    "thirtieth": 30,
    "thirty-first": 31,
    "thirty first": 31,
}

_WEEKDAY_RE = "|".join(_WEEKDAYS)
_MONTH_RE = "|".join(_MONTHS)


@dataclass(frozen=True, slots=True)
class TemporalResult:
    text: str
    instants: tuple[str, ...]
    ambiguous: bool
    needs_confirm: bool
    unresolved: bool


def resolve_relatives(text: str, now: datetime, zone: ZoneInfo) -> tuple[str, list[str]]:
    """Return ``(text, iso_instants)``. See ``resolve`` for flags."""
    result = resolve(text, now, zone)
    return result.text, list(result.instants)


def resolve(text: str, now: datetime, zone: ZoneInfo) -> TemporalResult:
    """Ground relative phrases in ``zone``. Relative phrases stay in ``text``.

    ``next WEEKDAY`` is the weekday of the following week, even when ``now``
    already falls on that weekday. Bare weekday is the next occurrence and
    may be today. Calendar arithmetic uses local midnights, not UTC hours.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(zone)
    lowered = text.lower()
    or_match = re.search(rf"\b({_WEEKDAY_RE})\s+or\s+({_WEEKDAY_RE})\b", lowered)
    if or_match is not None:
        first = _midnight(_next_or_today(local, _WEEKDAYS[or_match.group(1)]), zone)
        second = _midnight(_next_or_today(local, _WEEKDAYS[or_match.group(2)]), zone)
        instants = tuple(dict.fromkeys((first.isoformat(), second.isoformat())))
        return TemporalResult(
            text=text,
            instants=instants,
            ambiguous=len(instants) > 1,
            needs_confirm=False,
            unresolved=False,
        )
    next_match = re.search(rf"\bnext\s+({_WEEKDAY_RE})\b", lowered)
    if next_match is not None:
        target = _next_week(local, _WEEKDAYS[next_match.group(1)])
        return _single(text, _midnight(target, zone))
    this_match = re.search(rf"\bthis\s+({_WEEKDAY_RE})\b", lowered)
    if this_match is not None:
        target = _this_week(local, _WEEKDAYS[this_match.group(1)])
        return _single(text, _midnight(target, zone))
    if re.search(r"\bday after tomorrow\b", lowered):
        when = local.date() + timedelta(days=2)
        return _single(text, datetime.combine(when, time.min, tzinfo=zone))
    if re.search(r"\btomorrow\b", lowered):
        when = local.date() + timedelta(days=1)
        return _single(text, datetime.combine(when, time.min, tzinfo=zone))
    if re.search(r"\btoday\b", lowered):
        return _single(text, datetime.combine(local.date(), time.min, tzinfo=zone))
    bare = re.search(rf"\b({_WEEKDAY_RE})\b", lowered)
    if bare is not None:
        target = _next_or_today(local, _WEEKDAYS[bare.group(1)])
        return _single(text, _midnight(target, zone))
    month_day = _month_day(lowered, local, zone)
    if month_day is not None:
        instant, needs_confirm = month_day
        return TemporalResult(
            text=text,
            instants=(instant.isoformat(),),
            ambiguous=False,
            needs_confirm=needs_confirm,
            unresolved=False,
        )
    return TemporalResult(
        text=text,
        instants=(),
        ambiguous=False,
        needs_confirm=False,
        unresolved=True,
    )


def _single(text: str, instant: datetime) -> TemporalResult:
    return TemporalResult(
        text=text,
        instants=(instant.isoformat(),),
        ambiguous=False,
        needs_confirm=False,
        unresolved=False,
    )


def _midnight(when: datetime, zone: ZoneInfo) -> datetime:
    return datetime.combine(when.astimezone(zone).date(), time.min, tzinfo=zone)


def _next_week(local: datetime, weekday: int) -> datetime:
    delta = (weekday - local.weekday() + 7) % 7
    if delta == 0:
        delta = 7
    return local + timedelta(days=delta)


def _this_week(local: datetime, weekday: int) -> datetime:
    delta = (weekday - local.weekday()) % 7
    return local + timedelta(days=delta)


def _next_or_today(local: datetime, weekday: int) -> datetime:
    delta = (weekday - local.weekday()) % 7
    return local + timedelta(days=delta)


def _month_day(lowered: str, local: datetime, zone: ZoneInfo) -> tuple[datetime, bool] | None:
    ords = "|".join(re.escape(name) for name in sorted(_ORDINALS, key=len, reverse=True))
    pattern = rf"\b({_MONTH_RE})\s+(?:the\s+)?(\d{{1,2}}|{ords})\b"
    match = re.search(pattern, lowered)
    if match is None:
        return None
    month = _MONTHS[match.group(1)]
    day = _parse_day(match.group(2))
    year = local.year
    try:
        candidate = datetime(year, month, day, tzinfo=zone)
    except ValueError:
        return None
    if candidate.date() < local.date():
        try:
            candidate = datetime(year + 1, month, day, tzinfo=zone)
        except ValueError:
            return None
    needs_confirm = (candidate.date() - local.date()).days > 180
    return datetime.combine(candidate.date(), time.min, tzinfo=zone), needs_confirm


def _parse_day(raw: str) -> int:
    if raw.isdigit():
        return int(raw)
    dashed = raw.replace(" ", "-")
    if dashed in _ORDINALS:
        return _ORDINALS[dashed]
    return _ORDINALS[raw]
