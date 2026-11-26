"""YAML scenarios reject unknown intents and urgent scripts without a keyword."""

from pathlib import Path

import pytest
import yaml

from evals.schema import ScenarioError, load_scenario, load_smoke_ids


def test_examples_validate() -> None:
    root = Path("evals/scenarios/examples")
    ids = {"book_happy", "barge_mid_confirm", "noisy_name", "urgent_breathe", "faq_hours"}
    found = {path.stem for path in root.glob("*.yaml")}
    assert found == ids
    for path in root.glob("*.yaml"):
        scenario = load_scenario(path)
        assert scenario.caller == "scripted"


def test_unknown_intent_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    payload = {
        "id": "bad",
        "goal": "book",
        "intent": "not_an_intent",
        "slots": {},
        "persona": "brief",
        "speaking_rate": 1.0,
        "disfluency": False,
        "barge_in": False,
        "urgent": False,
        "clock": "virtual",
        "caller": "scripted",
        "script": ["hello"],
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ScenarioError, match="unknown intent"):
        load_scenario(path)


def test_missing_urgent_boolean_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    payload = {
        "id": "bad",
        "goal": "book",
        "intent": "book",
        "slots": {},
        "persona": "brief",
        "speaking_rate": 1.0,
        "disfluency": False,
        "barge_in": False,
        "clock": "virtual",
        "caller": "scripted",
        "script": ["hello"],
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ScenarioError, match="urgent"):
        load_scenario(path)


def test_urgent_without_keyword_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    payload = {
        "id": "bad",
        "goal": "urgent",
        "intent": "urgent_symptom",
        "slots": {},
        "persona": "brief",
        "speaking_rate": 1.0,
        "disfluency": False,
        "barge_in": False,
        "urgent": True,
        "clock": "virtual",
        "caller": "scripted",
        "script": ["I would like an appointment please"],
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ScenarioError, match="keyword"):
        load_scenario(path)


def test_smoke_list_has_ten_scripted_ids() -> None:
    ids = load_smoke_ids(Path("evals/scenarios/smoke.yaml"))
    assert len(ids) == 10
    assert "book_happy" in ids
    assert "urgent_breathe" in ids
