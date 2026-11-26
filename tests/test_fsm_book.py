"""Book path reaches CONFIRM without SQLite, then writes one row after yes."""

from pathlib import Path

from dialogue.context import StepContext
from dialogue.execute import start_iso_for, write_booking
from dialogue.proposal import apply_proposal
from dialogue.slots import confirmed_only
from models.llm_client import ProposalSchema
from tests.fsm_helpers import DOCTOR, NOW, TZ, book_slots, identity_slots, make_machine
from tools.calendar import appointment_count, load_appointment, migrate, seed_slot


def test_book_path_reaches_confirm_without_database() -> None:
    machine = make_machine()
    machine.start()
    machine.nlu(spoken="Jordan Pike 5550101234", intent="out_of_scope", slots=identity_slots())
    machine.nlu(spoken="book with Avery", intent="book", slots=book_slots())
    machine.nlu(spoken="book with Avery", intent="book", slots=book_slots())
    assert machine.history == [
        "GREET",
        "IDENTIFY_PATIENT",
        "COLLECT_INTENT",
        "COLLECT_SLOTS",
        "CONFIRM",
    ]
    assert machine.state.state_id == "CONFIRM"


def test_yes_writes_one_row(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, ("Dr. Avery Lang",))
    machine = make_machine()
    machine.start()
    machine.nlu(spoken="id", intent="out_of_scope", slots=identity_slots())
    machine.nlu(spoken="book", intent="book", slots=book_slots())
    machine.nlu(spoken="book", intent="book", slots=book_slots())
    assert machine.state.state_id == "CONFIRM"
    start = start_iso_for(machine.state, TZ)
    seed_slot(db, doctor_id=DOCTOR, start_iso=start, slot_id="S1", version=1)
    machine.state = machine.state.model_copy(update={"offered_slot_id": "S1", "offered_version": 1})
    machine.step(StepContext(event="yes", spoken="yes", settings=machine.settings))
    assert machine.state.state_id == "EXECUTE"
    result = write_booking(
        db,
        machine.state,
        session_id="11111111-1111-4111-8111-111111111111",
        turn_id=1,
        timezone=TZ,
    )
    assert result.ok
    assert appointment_count(db) == 1
    row = load_appointment(db, result.appointment_id)
    assert row["doctor_id"] == DOCTOR
    machine.step(
        StepContext(
            event="tool_ok",
            appointment_id=result.appointment_id,
            settings=machine.settings,
        )
    )
    assert machine.state.state_id == "CLOSE"
    assert confirmed_only(machine.state.slots)["doctor"] == DOCTOR


def test_proposal_does_not_insert(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, ("Dr. Avery Lang",))
    machine = make_machine()
    proposal = ProposalSchema(
        intent="book",
        slots={**book_slots(), "date": "2026-12-20"},
    )
    apply_proposal(
        machine.state,
        proposal,
        roster=machine.roster,
        now=NOW,
        timezone=TZ,
    )
    assert appointment_count(db) == 0
