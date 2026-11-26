"""Keyword hits escalate. NLU intent book cannot veto. Chest alone does not."""

from nlp.urgent import spoken_has_urgent
from tests.fsm_helpers import DOCTOR, identity_slots, make_machine


def test_keyword_list_hits_and_misses() -> None:
    assert spoken_has_urgent("I have chest pain") is True
    assert spoken_has_urgent("I can't breathe") is True
    assert spoken_has_urgent("I cannot breathe") is True
    assert spoken_has_urgent("shortness of breath today") is True
    assert spoken_has_urgent("chest") is False


def test_chest_pain_from_greet_is_urgent() -> None:
    machine = make_machine()
    machine.nlu(spoken="I have chest pain", intent="book", slots={})
    assert machine.state.state_id == "URGENT"
    assert machine.state.last_template == "seek_emergency"


def test_collect_slots_still_reaches_urgent() -> None:
    machine = make_machine()
    machine.start()
    machine.nlu(spoken="Jordan Pike 5550101234", intent="out_of_scope", slots=identity_slots())
    machine.nlu(spoken="book with Avery", intent="book", slots={"doctor": DOCTOR})
    assert machine.state.state_id == "COLLECT_SLOTS"
    machine.nlu(spoken="I had chest pain last year", intent="book", slots={})
    assert machine.state.state_id == "URGENT"


def test_nlu_book_cannot_veto_keyword() -> None:
    machine = make_machine()
    machine.start()
    machine.nlu(
        spoken="I can't breathe, book Tuesday",
        intent="book",
        slots={"doctor": DOCTOR},
    )
    assert machine.state.state_id == "URGENT"
    assert machine.history[-1] == "URGENT"
