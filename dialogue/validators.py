"""Phone, DOB, date, time, and doctor validators. No LLM calls."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from zoneinfo import ZoneInfo

_PHONE_RE = re.compile(r"^\d{10}$")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
_DOB = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def validate_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if _PHONE_RE.fullmatch(digits) is None:
        return "phone must be 10 digits"
    return None


def validate_dob(value: str, *, today: date) -> str | None:
    parsed = _parse_iso_date(value)
    if parsed is None:
        return "dob must be an ISO date"
    if parsed > today:
        return "dob is in the future"
    return None


def validate_date(value: str, *, today: date) -> str | None:
    """ISO calendar date, not past in the clinic timezone. Relative words fail."""
    parsed = _parse_iso_date(value)
    if parsed is None:
        return "date must be an ISO instant or ISO date"
    if parsed < today:
        return "date is in the past"
    return None


def validate_time(value: str) -> str | None:
    match = _ISO_TIME.fullmatch(value.strip())
    if match is None:
        return "time must be HH:MM"
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return "time is out of range"
    if minute % 5 != 0:
        return "time must land on a 5-minute grid"
    return None


def validate_doctor(value: str, roster: tuple[str, ...]) -> str | None:
    if value not in roster:
        return "doctor is not in the roster"
    return None


def validate_iso_datetime(value: str) -> str | None:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return "value is not ISO"
    return None


def validate_slot(
    key: str,
    value: str,
    *,
    roster: tuple[str, ...],
    now: datetime,
    timezone: ZoneInfo,
) -> str | None:
    """Return an error string or None. The validator does not call the LLM."""
    stripped = value.strip()
    if not stripped:
        return f"{key} is empty"
    today = now.astimezone(timezone).date()
    if key == "phone":
        return validate_phone(stripped)
    if key == "dob":
        return validate_dob(stripped, today=today)
    if key == "date":
        return validate_date(stripped, today=today)
    if key == "time":
        return validate_time(stripped)
    if key == "doctor":
        return validate_doctor(stripped, roster)
    if key in {"patient_name", "reason", "faq_query", "appointment_id"}:
        return None
    return None


def invalid_slot_keys(
    slots: Mapping[str, object],
    *,
    roster: tuple[str, ...],
    now: datetime,
    timezone: ZoneInfo,
) -> list[str]:
    """Keys whose current values fail ``validate_slot``."""
    bad: list[str] = []
    for key, item in slots.items():
        value = getattr(item, "value", None)
        if not isinstance(value, str):
            continue
        if validate_slot(key, value, roster=roster, now=now, timezone=timezone) is not None:
            bad.append(key)
    return bad


def _parse_iso_date(value: str) -> date | None:
    match = _ISO_DATE.fullmatch(value.strip())
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
