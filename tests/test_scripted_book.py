"""Scripted caller books the expected doctor and time through the FSM."""

from pathlib import Path

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.schema import load_scenario


async def test_scripted_book_writes_expected_row(tmp_path: Path) -> None:
    scenario = load_scenario(Path("evals/scenarios/smoke/book_avery.yaml"))
    settings = default_eval_settings()
    db = tmp_path / "clinic.sqlite"
    trace = await run_scripted(scenario, db=db, settings=settings)
    judged = judge(scenario, trace, settings=settings)
    assert judged.success is True
    assert judged.appointment_id
    assert trace.appointments[0]["doctor_id"] == "Dr. Avery Lang"
