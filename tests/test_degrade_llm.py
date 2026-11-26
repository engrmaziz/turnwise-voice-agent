"""LLM-down still books through templates. The client is unavailable on the product path."""

from pathlib import Path

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.schema import load_scenario
from models.llm_client import LlmClient


async def test_unavailable_llm_still_writes_one_row(tmp_path: Path) -> None:
    scenario = load_scenario(Path("evals/scenarios/smoke/book_avery.yaml"))
    settings = default_eval_settings()
    llm = LlmClient.unavailable(timeout_ms=settings.llm_health_timeout_ms)
    assert llm.available is False
    db = tmp_path / "clinic.sqlite"
    trace = await run_scripted(scenario, db=db, settings=settings)
    judged = judge(scenario, trace, settings=settings)
    assert judged.success is True
    assert len(trace.appointments) == 1
