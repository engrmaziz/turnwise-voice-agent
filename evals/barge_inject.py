"""Inject barge-in while the agent is in SAY. Scripted path, not a live phone."""

from __future__ import annotations

from evals.schema import Scenario
from pipeline.session import Session


def inject_barge(session: Session, scenario: Scenario) -> bool:
    """Return True when the session actually cancelled. Requires AEC enabled."""
    if not scenario.barge_in:
        return False
    return session.request_barge_in()
