"""Caller scripts reject unknown intents and appendix-D slot keys."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nlp.hotwords import load_roster
from nlp.nlu_vocab import INTENTS
from training.nlu.generate import generate_scripts, load_jsonl
from training.nlu.schema import CallerScript


def test_rejects_unknown_intent() -> None:
    with pytest.raises(ValidationError, match="unknown intent"):
        CallerScript(
            script_id="s1",
            intent="order_pizza",
            slots={},
            persona="brief",
            disfluency=False,
            text="hello",
        )


def test_rejects_slot_not_in_appendix_d() -> None:
    with pytest.raises(ValidationError, match="slot not in appendix D"):
        CallerScript(
            script_id="s1",
            intent="book",
            slots={"favorite_color": "blue"},
            persona="brief",
            disfluency=False,
            text="book tuesday",
        )


def test_two_hundred_hand_authored_cover_intents() -> None:
    roster = load_roster(Path("data/doctors.txt"))
    scripts = generate_scripts(count=200, roster=roster)
    counts: dict[str, int] = {}
    for script in scripts:
        counts[script.intent] = counts.get(script.intent, 0) + 1
    for intent, n in counts.items():
        assert n >= 10, intent
    assert len(scripts) == 200


def test_fixture_scripts_cover_every_intent() -> None:
    path = Path("training/nlu/fixture_scripts.jsonl")
    scripts = load_jsonl(path)
    assert len(scripts) == 20
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert "hand_authored" in header
    assert {script.intent for script in scripts} == set(INTENTS)
