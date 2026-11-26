"""Scripted caller. Walks a scenario without a language model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evals.schema import Scenario
from nlp.hotwords import load_roster
from nlp.phonetic import resolve_entity
from nlp.urgent import spoken_has_urgent
from server.config import Settings

_YES = frozenset({"yes", "yeah", "yep", "correct", "that's right", "thats right"})


@dataclass(slots=True, frozen=True)
class ScriptTurn:
    spoken: str
    intent: str
    slots: dict[str, str]


def resolve_roster_doctor(raw: str, roster: tuple[str, ...], settings: Settings) -> str:
    stripped = raw.strip()
    if stripped in roster:
        return stripped
    result = resolve_entity(stripped, list(roster), settings)
    if result.entity_id:
        return result.entity_id
    folded = stripped.casefold()
    for name in roster:
        if folded and folded in name.casefold():
            return name
    return stripped


def scripted_turns(scenario: Scenario, settings: Settings) -> tuple[ScriptTurn, ...]:
    """Expand YAML script into NLU turns the eval harness injects.

    Production WebSocket does not implement this path. Identity is prepended for
    book goals because the FSM is identity-first; appendix F scripts name then
    phone after the book line.
    """
    roster = load_roster(Path(settings.doctor_roster_path))
    slots = dict(scenario.slots)
    if "doctor" in slots:
        slots["doctor"] = resolve_roster_doctor(slots["doctor"], roster, settings)
    if scenario.goal == "faq":
        query = slots.get("faq_query") or (scenario.script[0] if scenario.script else "")
        spoken = scenario.script[0] if scenario.script else query
        identity = ScriptTurn(
            spoken="Ada Lovelace 5550100123",
            intent="out_of_scope",
            slots={"patient_name": "Ada Lovelace", "phone": "5550100123"},
        )
        return (
            identity,
            ScriptTurn(spoken=spoken, intent="faq", slots={"faq_query": query}),
        )
    if scenario.goal == "urgent":
        spoken = scenario.script[0] if scenario.script else "I can't breathe"
        return (ScriptTurn(spoken=spoken, intent="book", slots={}),)
    if scenario.goal == "handoff":
        spoken = scenario.script[0] if scenario.script else "speak to a human"
        return (ScriptTurn(spoken=spoken, intent="speak_to_human", slots={}),)
    turns: list[ScriptTurn] = []
    if scenario.goal in {"book", "reschedule", "cancel", "check"}:
        name = slots.get("patient_name", "")
        phone = slots.get("phone", "")
        if name and phone:
            turns.append(
                ScriptTurn(
                    spoken=f"{name} {phone}",
                    intent="out_of_scope",
                    slots={"patient_name": name, "phone": phone},
                )
            )
    wants_yes = any(line.strip().casefold() in _YES for line in scenario.script)
    book_line = next(
        (line for line in scenario.script if line.strip().casefold() not in _YES),
        scenario.script[0] if scenario.script else scenario.goal,
    )
    if scenario.goal == "book":
        payload: dict[str, str] = {
            key: slots[key]
            for key in ("patient_name", "phone", "doctor", "date", "time")
            if key in slots
        }
        turns.append(ScriptTurn(spoken=book_line, intent="book", slots=payload))
        turns.append(ScriptTurn(spoken=book_line, intent="book", slots=payload))
        if wants_yes:
            turns.append(ScriptTurn(spoken="yes", intent="yes", slots={}))
        return tuple(turns)
    if scenario.goal in {"cancel", "reschedule", "check"}:
        spoken = scenario.script[0] if scenario.script else scenario.goal
        turns.append(ScriptTurn(spoken=spoken, intent=scenario.intent, slots=slots))
        return tuple(turns)
    for line in scenario.script:
        intent = scenario.intent
        if spoken_has_urgent(line):
            intent = "book"
        turns.append(ScriptTurn(spoken=line, intent=intent, slots=slots))
    return tuple(turns)
