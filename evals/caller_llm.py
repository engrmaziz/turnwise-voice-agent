"""LLM spoken caller. Persona, not an oracle. CI does not run this path."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from evals.schema import Scenario
from models.llm_client import LlmClient, LlmGrammarError, parse_grammar

_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class CallerUtterance(BaseModel):
    """Next utterance. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    done: bool = False


def reject_leaked_dates(text: str, allowed_dates: tuple[str, ...]) -> None:
    """The caller is not an oracle. Hidden ISO dates in the reply are a grammar fail."""
    allowed = set(allowed_dates)
    for match in _ISO_DATE.findall(text):
        if match not in allowed:
            raise LlmGrammarError("caller must not leak an ISO date the scenario hid")


def parse_caller_reply(raw: str, *, allowed_dates: tuple[str, ...]) -> CallerUtterance:
    payload = parse_grammar(raw, CallerUtterance)
    reply = CallerUtterance.model_validate(payload)
    reject_leaked_dates(reply.text, allowed_dates)
    return reply


async def next_utterance(
    scenario: Scenario,
    *,
    agent_text: str,
    llm: LlmClient,
) -> CallerUtterance:
    if not llm.available:
        raise LlmGrammarError("llm caller blocked")
    allowed = tuple(value for key, value in scenario.slots.items() if key == "date" and value)
    prompt = (
        f"You are a clinic caller with persona {scenario.persona}. "
        f"Goal: {scenario.goal}. You do not know the database. "
        f"Agent said: {agent_text}. Reply JSON {{text, done}}."
    )
    payload = await llm.complete_json(prompt, CallerUtterance)
    reply = CallerUtterance.model_validate(payload)
    reject_leaked_dates(reply.text, allowed)
    return reply
