"""Inputs to one FSM step. Guards read this; they do not write the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from server.config import Settings


@dataclass(slots=True)
class StepContext:
    event: str
    spoken: str = ""
    intent: str = ""
    nlu_slots: dict[str, str] = field(default_factory=dict)
    nlu_conf: dict[str, float] = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)
    roster: tuple[str, ...] = ()
    now: datetime | None = None
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/New_York"))
    faq_chunk_id: str = ""
    faq_reply: str = ""
    appointment_id: str = ""
    conflict_alts: tuple[str, ...] = ()
    offer_latched: bool = False
    source: str = "nlu"
