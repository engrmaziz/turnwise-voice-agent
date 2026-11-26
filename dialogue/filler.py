"""Spoken filler at tool_filler_after_ms. Sets payload filler=1 for phase 7."""

from __future__ import annotations

from pipeline.event import Event, EventKind
from pipeline.session import Session


def filler_event(session: Session, *, template_id: str = "one_moment") -> Event:
    return session.create_event(
        EventKind.SAY,
        {"template_id": template_id, "text": "One moment.", "filler": 1},
    )
