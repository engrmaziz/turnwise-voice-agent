"""Load the transition table and apply one event. Illegal events stay put."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from dialogue.actions import ACTIONS
from dialogue.context import StepContext
from dialogue.guards import BOOKING_INTENTS, GUARDS
from dialogue.slots import DialogueState
from nlp.urgent import keyword_list, spoken_has_urgent
from server.config import Settings

RejectFn = Callable[[str], object]
TransitionFn = Callable[[str, str], object]

TABLE_PATH = Path(__file__).resolve().parent / "transitions.toml"

_YES = frozenset({"yes", "yeah", "yep", "correct", "that's right", "thats right"})
_NO = frozenset({"no", "nope", "wrong", "incorrect"})
_BYE = frozenset({"goodbye", "bye", "that's all", "thats all", "nothing else"})


class Transition(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: str
    event: str
    guard: str
    action: str
    next_state: str
    except_states: tuple[str, ...] = ()


@dataclass(slots=True)
class Table:
    states: tuple[str, ...]
    rows: tuple[Transition, ...]


def load_table(path: Path | None = None) -> Table:
    target = path if path is not None else TABLE_PATH
    payload = tomllib.loads(target.read_text(encoding="utf-8"))
    states = tuple(str(item) for item in payload["states"])
    state_set = set(states)
    rows: list[Transition] = []
    for raw in payload["row"]:
        if not isinstance(raw, dict):
            raise ValueError("transition row must be a table")
        row = _parse_row(raw)
        if row.guard not in GUARDS:
            raise ValueError(f"unknown guard: {row.guard}")
        if row.action not in ACTIONS:
            raise ValueError(f"unknown action: {row.action}")
        except_set = set(row.except_states)
        if row.state == "*":
            for state in states:
                if state in except_set:
                    continue
                expanded = Transition(
                    state=state,
                    event=row.event,
                    guard=row.guard,
                    action=row.action,
                    next_state=row.next_state,
                )
                _check_next(expanded, state_set)
                rows.append(expanded)
            continue
        if row.state not in state_set:
            raise ValueError(f"unknown state: {row.state}")
        _check_next(row, state_set)
        rows.append(row)
    return Table(states=states, rows=tuple(rows))


def apply_event(
    table: Table,
    state: DialogueState,
    ctx: StepContext,
    *,
    on_reject: RejectFn | None = None,
    on_transition: TransitionFn | None = None,
) -> DialogueState:
    """Return a new state, or the same object when no row matches."""
    incoming = ctx.event
    exact = [row for row in table.rows if row.state == state.state_id and row.event == incoming]
    wildcard = [row for row in table.rows if row.state == state.state_id and row.event == "any"]
    for row in exact + wildcard:
        guard = GUARDS[row.guard]
        if not guard(state, ctx):
            continue
        action = ACTIONS[row.action]
        updated = action(state, ctx)
        next_state = updated.model_copy(
            update={
                "state_id": row.next_state,
                "last_guard": row.guard,
                "last_action": row.action,
            }
        )
        if on_transition is not None:
            on_transition(state.state_id, row.next_state)
        return next_state
    if on_reject is not None:
        on_reject("no_row")
    return state


def classify_event(
    state: DialogueState,
    *,
    spoken: str,
    intent: str,
    settings: Settings,
) -> str:
    """Map an NLU payload onto a table event. Keywords win over intent."""
    if state.state_id != "URGENT" and spoken_has_urgent(spoken, keyword_list(settings)):
        return "urgent_keyword"
    if state.state_id != "HANDOFF" and intent == "speak_to_human":
        return "speak_to_human"
    lowered = spoken.strip().casefold()
    if state.state_id == "CONFIRM" and lowered in _YES:
        return "yes"
    if state.state_id == "CONFIRM" and lowered in _NO:
        return "no"
    if intent in {"yes"} or (lowered in _YES and state.state_id == "CONFIRM"):
        return "yes"
    if lowered in _BYE and state.state_id == "CLOSE":
        return "goodbye"
    if intent in BOOKING_INTENTS or intent in {"faq", "out_of_scope"}:
        return "nlu"
    if intent == "urgent_symptom":
        return "urgent_keyword"
    if lowered in _YES and state.state_id == "CONFIRM":
        return "yes"
    return "nlu"


def _parse_row(raw: dict[str, Any]) -> Transition:
    except_raw = raw.get("except", [])
    except_states = tuple(str(item) for item in except_raw) if isinstance(except_raw, list) else ()
    return Transition(
        state=str(raw["state"]),
        event=str(raw["event"]),
        guard=str(raw.get("guard", "none")),
        action=str(raw["action"]),
        next_state=str(raw["next_state"]),
        except_states=except_states,
    )


def _check_next(row: Transition, states: set[str]) -> None:
    if row.next_state not in states:
        raise ValueError(f"next_state {row.next_state} is not in the state list")
