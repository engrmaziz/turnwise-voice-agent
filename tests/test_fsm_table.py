"""Illegal events stay in the same state. Unknown guards fail at load."""

from pathlib import Path

import pytest

from dialogue.diagram import normalize, render_mermaid
from dialogue.table import load_table
from tests.fsm_helpers import make_machine


def test_unknown_event_returns_same_state() -> None:
    machine = make_machine()
    machine.start()
    before = machine.state
    from dialogue.context import StepContext

    nxt = machine.step(StepContext(event="not_a_real_event", settings=machine.settings))
    assert nxt is before
    assert nxt.state_id == before.state_id


def test_unknown_guard_fails_at_startup(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        'states = ["GREET", "URGENT"]\n'
        "[[row]]\n"
        'state = "GREET"\n'
        'event = "session_start"\n'
        'guard = "not_a_guard"\n'
        'action = "say_greeting"\n'
        'next_state = "GREET"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown guard"):
        load_table(path)


def test_unknown_next_state_fails_at_startup(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        'states = ["GREET"]\n'
        "[[row]]\n"
        'state = "GREET"\n'
        'event = "session_start"\n'
        'guard = "none"\n'
        'action = "say_greeting"\n'
        'next_state = "NOWHERE"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="next_state"):
        load_table(path)


def test_unknown_action_fails_at_startup(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        'states = ["GREET"]\n'
        "[[row]]\n"
        'state = "GREET"\n'
        'event = "session_start"\n'
        'guard = "none"\n'
        'action = "not_an_action"\n'
        'next_state = "GREET"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown action"):
        load_table(path)


def test_diagram_matches_appendix_c() -> None:
    text = Path("docs/plan/11_appendices.md").read_text(encoding="utf-8")
    marker = "```mermaid"
    start = text.index(marker) + len(marker)
    end = text.index("```", start)
    appendix = text[start:end]
    assert normalize(render_mermaid()) == normalize(appendix)
