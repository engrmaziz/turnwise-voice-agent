"""Politeness and clarity only. Nested under task_success; cannot flip it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from evals.judge_db import DbJudgement
from models.llm_client import LlmClient, LlmGrammarError, LlmTimeoutError


class SoftScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    politeness: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)


class CombinedReport:
    __slots__ = ("reason", "soft", "task_success")

    def __init__(
        self,
        *,
        task_success: bool,
        reason: str,
        soft: SoftScores | None,
    ) -> None:
        self.task_success = task_success
        self.reason = reason
        self.soft = soft


async def combine(
    judgement: DbJudgement,
    *,
    llm: LlmClient | None,
    transcript: str,
    enabled: bool,
) -> CombinedReport:
    """Soft scores are nested. A stub 0/5 does not change task_success."""
    soft: SoftScores | None = None
    if enabled and llm is not None and llm.available:
        try:
            payload = await llm.complete_json(
                f"Score politeness and clarity 0-5 for: {transcript}",
                SoftScores,
            )
            soft = SoftScores.model_validate(payload)
        except (LlmGrammarError, LlmTimeoutError):
            soft = None
    return CombinedReport(
        task_success=judgement.success,
        reason=judgement.reason,
        soft=soft,
    )
