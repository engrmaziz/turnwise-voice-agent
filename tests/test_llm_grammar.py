"""Non-JSON LLM output is a typed error, not a regex scrape."""

import pytest
from pydantic import BaseModel, ConfigDict

from dialogue.planner import speak
from models.llm_client import LlmClient, LlmGrammarError, parse_grammar
from server.config import Settings


class _Tiny(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str


def test_non_json_is_typed_error() -> None:
    with pytest.raises(LlmGrammarError, match="non-json"):
        parse_grammar("not-json {intent}", _Tiny)


async def test_overlong_paraphrase_keeps_template() -> None:
    blob = '{"text": "' + ("x" * 500) + '"}'
    llm = LlmClient.stub(timeout_ms=2000, response=blob)
    spoken = await speak(
        "greet",
        fallback="Hello, this is Turnwise Clinic.",
        settings=Settings(),
        llm=llm,
        paraphrase=True,
    )
    assert spoken == "Hello, this is Turnwise Clinic."
    assert len(spoken) < 180
