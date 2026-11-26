"""LLM caller grammar rejects a leaked ISO date the scenario did not allow."""

import pytest

from evals.caller_llm import parse_caller_reply
from models.llm_client import LlmGrammarError


def test_leaked_iso_date_is_rejected() -> None:
    raw = '{"text": "book me on 2026-03-10", "done": false}'
    with pytest.raises(LlmGrammarError, match="ISO date"):
        parse_caller_reply(raw, allowed_dates=())


def test_allowed_date_passes() -> None:
    raw = '{"text": "book me on 2026-03-10", "done": false}'
    reply = parse_caller_reply(raw, allowed_dates=("2026-03-10",))
    assert "2026-03-10" in reply.text
