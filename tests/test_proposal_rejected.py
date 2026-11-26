"""A proposal with a relative date is rejected. This module must not import calendar."""

from pathlib import Path

import pytest

from dialogue.proposal import ProposalRejected, apply_proposal, parse_proposal
from dialogue.slots import DialogueState
from models.llm_client import ProposalSchema
from tests.fsm_helpers import NOW, TZ, make_machine


def test_tomorrow_is_rejected() -> None:
    state = DialogueState()
    proposal = ProposalSchema(intent="book", slots={"date": "tomorrow"})
    nxt = apply_proposal(state, proposal, roster=("Dr. Avery Lang",), now=NOW, timezone=TZ)
    assert nxt is state


def test_extra_field_is_rejected() -> None:
    with pytest.raises(ProposalRejected, match="extra field"):
        parse_proposal({"intent": "book", "slots": {}, "calendar": True})


def test_ignore_instructions_fails_iso_or_oos() -> None:
    machine = make_machine()
    proposal = parse_proposal(
        {
            "intent": "book",
            "slots": {"date": "tomorrow", "time": "noon"},
        }
    )
    nxt = apply_proposal(
        machine.state,
        proposal,
        roster=machine.roster,
        now=NOW,
        timezone=TZ,
    )
    assert nxt is machine.state


def test_this_module_does_not_import_calendar() -> None:
    src = Path("dialogue/proposal.py").read_text(encoding="utf-8")
    imports = [line for line in src.splitlines() if line.startswith(("import ", "from "))]
    assert not any("calendar" in line for line in imports)
