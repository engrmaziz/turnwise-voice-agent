"""Clinic-zone calendar arithmetic. Not UTC hour offsets, not an LLM."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from nlp.temporal import resolve
from server.config import Settings

_ZONE = ZoneInfo("America/New_York")


def test_next_tuesday_from_tuesday_is_next_week() -> None:
    now = datetime(2026, 3, 3, 9, 0, tzinfo=_ZONE)
    result = resolve("next Tuesday", now, _ZONE)
    expected = datetime(2026, 3, 10, 0, 0, tzinfo=_ZONE).isoformat()
    assert result.instants == (expected,)
    assert result.unresolved is False


def test_day_after_tomorrow_uses_two_midnights_not_utc_hours() -> None:
    now = datetime(2026, 3, 7, 18, 0, tzinfo=_ZONE)
    result = resolve("day after tomorrow", now, _ZONE)
    grounded = datetime.fromisoformat(result.instants[0])
    assert grounded.date().isoformat() == "2026-03-09"
    assert grounded.hour == 0
    plus_48h = (now.astimezone(UTC) + timedelta(hours=48)).astimezone(_ZONE)
    assert grounded != plus_48h


def test_sometime_is_unresolved() -> None:
    now = datetime(2026, 3, 3, 9, 0, tzinfo=_ZONE)
    result = resolve("sometime", now, _ZONE)
    assert result.instants == ()
    assert result.unresolved is True


def test_or_is_ambiguous() -> None:
    now = datetime(2026, 3, 3, 9, 0, tzinfo=_ZONE)
    result = resolve("Tuesday or Wednesday", now, _ZONE)
    assert result.ambiguous is True
    assert len(result.instants) == 2


def test_unknown_timezone_fails_at_settings() -> None:
    with pytest.raises(ValidationError, match="unknown timezone"):
        Settings(clinic_timezone="Not/AZone")
