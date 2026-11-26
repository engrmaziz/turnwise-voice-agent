"""Every FSM action has a template. Missing keys fail at load."""

from pathlib import Path

import pytest

from dialogue.actions import ACTIONS
from dialogue.planner import select_template_text
from dialogue.slots import DialogueState, SlotValue
from dialogue.templates import load_templates


def test_every_action_has_a_template() -> None:
    catalog = load_templates()
    assert set(catalog.by_action) == set(ACTIONS)
    for action in ACTIONS:
        tmpl = catalog.require_action(action)
        assert tmpl.text.strip()


def test_missing_action_fails_load(tmp_path: Path) -> None:
    src = Path("dialogue/templates.toml").read_text(encoding="utf-8")
    src = src.replace('[say_goodbye]\nid = "goodbye"\ntext = "Goodbye."\n', "")
    path = tmp_path / "templates.toml"
    path.write_text(src, encoding="utf-8")
    with pytest.raises(ValueError, match="missing template"):
        load_templates(path)


def test_unknown_action_fails_load(tmp_path: Path) -> None:
    src = Path("dialogue/templates.toml").read_text(encoding="utf-8")
    src += '\n[not_an_action]\nid = "x"\ntext = "nope"\n'
    path = tmp_path / "templates.toml"
    path.write_text(src, encoding="utf-8")
    with pytest.raises(ValueError, match="unknown template"):
        load_templates(path)


def test_pending_slot_is_empty_and_ask_variant_is_used() -> None:
    state = DialogueState(
        intent="book",
        last_action="ask_slot",
        last_template="ask_slot",
        slots={"doctor": SlotValue(value="Khan", status="pending")},
    )
    template_id, text = select_template_text("ask_slot", state)
    assert template_id == "ask_slot"
    assert "Khan" not in text
    assert "I still need" in text


def test_short_variants_for_ask_and_confirm() -> None:
    catalog = load_templates()
    assert catalog.require_action("ask_slot").short
    assert catalog.require_action("confirm").short
    assert catalog.require_action("offer_human").text == "Would you like me to get a person?"
