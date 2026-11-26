"""Deterministic slot matcher kept for ablation T9.5.4.

Not imported by ``server.app``. Phase 5's default path is the NLU student.
"""

from __future__ import annotations

import re

from nlp.hotwords import load_roster
from nlp.nlu_features import tokenize
from nlp.phonetic import strip_title

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_PHONE = re.compile(r"\b\d{10}\b")
_APPT = re.compile(r"\bA\d{4}\b", re.IGNORECASE)


def match_slots(text: str, roster: tuple[str, ...]) -> dict[str, str]:
    """Extract closed-set doctors, a weekday, a 10-digit phone, and an id.

    This is the week-6 matcher. The student, not this function, is on the
    live NLU path.
    """
    slots: dict[str, str] = {}
    lowered = text.lower()
    for name in roster:
        bare = strip_title(name)
        if bare and bare in lowered:
            slots["doctor"] = name
            break
    tokens = [tok.lower() for tok in tokenize(text)]
    for day in _WEEKDAYS:
        if day in tokens:
            slots["date"] = day
            break
    phone = _PHONE.search(text)
    if phone is not None:
        slots["phone"] = phone.group(0)
    appt = _APPT.search(text)
    if appt is not None:
        slots["appointment_id"] = appt.group(0).upper()
    return slots


def roster_from_default() -> tuple[str, ...]:
    from pathlib import Path

    return load_roster(Path("data/doctors.txt"))
