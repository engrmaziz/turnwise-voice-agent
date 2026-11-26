"""Eval scenario schema. YAML that cannot fire its own urgent path is rejected."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nlp.nlu_vocab import INTENTS
from nlp.urgent import spoken_has_urgent

GOALS = frozenset({"book", "reschedule", "cancel", "check", "faq", "urgent", "handoff"})
CLOCKS = frozenset({"virtual", "realtime"})
CALLERS = frozenset({"scripted", "llm"})


class ScenarioError(ValueError):
    """Scenario YAML failed closed-set checks."""


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    goal: str
    intent: str
    slots: dict[str, str] = Field(default_factory=dict)
    persona: str = Field(min_length=1)
    noise_snr_db: float | None = None
    speaking_rate: float = 1.0
    disfluency: bool
    barge_in: bool
    urgent: bool
    clock: str
    caller: str
    script: tuple[str, ...] = ()
    barge_at_play_frame: int | None = None
    barge_text: str = ""

    @field_validator("goal")
    @classmethod
    def known_goal(cls, value: str) -> str:
        if value not in GOALS:
            raise ValueError(f"unknown goal {value}")
        return value

    @field_validator("intent")
    @classmethod
    def known_intent(cls, value: str) -> str:
        if value not in INTENTS:
            raise ValueError(f"unknown intent {value}")
        return value

    @field_validator("clock")
    @classmethod
    def known_clock(cls, value: str) -> str:
        if value not in CLOCKS:
            raise ValueError("clock must be virtual or realtime")
        return value

    @field_validator("caller")
    @classmethod
    def known_caller(cls, value: str) -> str:
        if value not in CALLERS:
            raise ValueError("caller must be scripted or llm")
        return value

    @field_validator("speaking_rate")
    @classmethod
    def known_rate(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("speaking_rate must be > 0")
        return value


def load_scenario(path: Path) -> Scenario:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ScenarioError("scenario must be a mapping")
    try:
        scenario = Scenario.model_validate(_normalize(raw))
    except Exception as exc:
        raise ScenarioError(str(exc)) from exc
    _check_urgent(scenario)
    return scenario


def load_smoke_ids(path: Path) -> tuple[str, ...]:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "ids" not in raw:
        raise ScenarioError("smoke.yaml must have ids")
    ids = raw["ids"]
    if not isinstance(ids, list) or not ids:
        raise ScenarioError("smoke ids must be a non-empty list")
    return tuple(str(item) for item in ids)


def find_scenario(root: Path, scenario_id: str) -> Path:
    matches = list(root.rglob(f"{scenario_id}.yaml"))
    if not matches:
        raise ScenarioError(f"missing scenario {scenario_id}")
    return matches[0]


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw)
    script = payload.get("script", [])
    if script is None:
        payload["script"] = ()
    elif isinstance(script, list):
        payload["script"] = tuple(str(item) for item in script)
    return payload


def _check_urgent(scenario: Scenario) -> None:
    if not scenario.urgent:
        return
    spoken = " ".join(scenario.script)
    if not spoken_has_urgent(spoken):
        raise ScenarioError("urgent scenario lacks a keyword")
