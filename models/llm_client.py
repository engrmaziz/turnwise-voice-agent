"""LLM client. Structured output is grammar-constrained JSON, never regex-scraped."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

_LOG = structlog.get_logger("models.llm_client")


class LlmGrammarError(Exception):
    """Model output was not valid JSON for the requested schema."""


class LlmTimeoutError(Exception):
    """The client exceeded llm_timeout_ms."""


class ProposalSchema(BaseModel):
    """Closed proposal object. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    slots: dict[str, str]


LlmFn = Callable[[str], str]


@dataclass(slots=True)
class LlmClient:
    """Process-wide client. Missing binaries use the stub path."""

    timeout_s: float
    complete_sync: LlmFn | None
    available: bool
    model_name: str = "unavailable"

    @classmethod
    def unavailable(cls, *, timeout_ms: int) -> LlmClient:
        return cls(timeout_s=timeout_ms / 1000.0, complete_sync=None, available=False)

    @classmethod
    def stub(cls, *, timeout_ms: int, response: str, sleep_s: float = 0.0) -> LlmClient:
        def complete_sync(_prompt: str) -> str:
            if sleep_s > 0:
                import time

                time.sleep(sleep_s)
            return response

        return cls(
            timeout_s=timeout_ms / 1000.0,
            complete_sync=complete_sync,
            available=True,
            model_name="stub",
        )

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        if not self.available or self.complete_sync is None:
            raise LlmGrammarError("llm unavailable")
        loop = asyncio.get_running_loop()
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, self.complete_sync, prompt),
                timeout=self.timeout_s,
            )
        except TimeoutError as exc:
            _LOG.warning("llm_timeout", timeout_s=self.timeout_s)
            raise LlmTimeoutError("llm timeout") from exc
        return parse_grammar(raw, schema)


def parse_grammar(raw: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Typed error on non-JSON. No regex scrape of free text."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmGrammarError("non-json") from exc
    try:
        parsed = schema.model_validate(payload)
    except ValidationError as exc:
        raise LlmGrammarError("schema") from exc
    return parsed.model_dump()
