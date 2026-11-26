"""A soft judge of 0/5 cannot flip task_success."""

from evals.judge_db import DbJudgement
from evals.judge_soft import combine
from models.llm_client import LlmClient


async def test_stub_zero_does_not_override_success() -> None:
    judgement = DbJudgement(
        success=True,
        reason="booked",
        appointment_id="A1",
        expected={},
        actual={},
    )
    llm = LlmClient.stub(timeout_ms=50, response='{"politeness": 0, "clarity": 0}')
    report = await combine(judgement, llm=llm, transcript="hello", enabled=True)
    assert report.task_success is True
    assert report.soft is not None
    assert report.soft.politeness == 0


async def test_stub_five_does_not_override_failure() -> None:
    judgement = DbJudgement(
        success=False,
        reason="wrong_doctor",
        appointment_id="A1",
        expected={"doctor": "Dr. Avery Lang"},
        actual={"doctor": "Dr. Khan"},
    )
    llm = LlmClient.stub(timeout_ms=50, response='{"politeness": 5, "clarity": 5}')
    report = await combine(judgement, llm=llm, transcript="sorry", enabled=True)
    assert report.task_success is False
    assert report.soft is not None
    assert report.soft.politeness == 5
