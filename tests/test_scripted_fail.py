"""A hang-up before confirm leaves no appointment row."""

from pathlib import Path

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.schema import load_scenario


async def test_hangup_early_expects_no_row(tmp_path: Path) -> None:
    scenario = load_scenario(Path("evals/scenarios/smoke/hangup_early.yaml"))
    settings = default_eval_settings()
    db = tmp_path / "clinic.sqlite"
    trace = await run_scripted(scenario, db=db, settings=settings)
    judged = judge(scenario, trace, settings=settings)
    assert judged.success is False
    assert judged.reason == "no_appointment"
    assert trace.appointments == []
