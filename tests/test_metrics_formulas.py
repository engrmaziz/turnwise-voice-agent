"""Tiny-fixture p50 uses the even-n midpoint."""

from evals.judge_db import DbJudgement
from evals.metrics import ESTIMATOR, percentile, task_success


def test_even_n_p50_is_midpoint() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert ESTIMATOR == "midpoint_even_nearest_rank_odd"


def test_task_success_rate() -> None:
    rows = [
        DbJudgement(success=True, reason="ok", appointment_id=None, expected={}, actual={}),
        DbJudgement(success=False, reason="no", appointment_id=None, expected={}, actual={}),
    ]
    assert task_success(rows) == 0.5
