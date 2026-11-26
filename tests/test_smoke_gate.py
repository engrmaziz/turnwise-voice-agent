"""Smoke gate uses slack on task success. Missing realtime does not fail TTFA."""

import json
from pathlib import Path

import pytest

from evals.smoke_gate import SmokeGateError, apply_gate


def test_drop_beyond_slack_fails() -> None:
    current = {"task_success": 0.5, "n": 10}
    previous = {"task_success": 0.9, "n": 10}
    with pytest.raises(SmokeGateError):
        apply_gate(current, previous, None)


def test_missing_realtime_does_not_fail_ttfa() -> None:
    current = {"task_success": 0.9, "n": 10}
    previous = {"task_success": 0.9, "n": 10}
    apply_gate(current, previous, {"status": "skipped", "n": 0})


def test_realtime_p95_over_cap_fails(tmp_path: Path) -> None:
    current = {"task_success": 0.9, "n": 10}
    realtime = {"status": "ok", "n": 30, "ttfa_p95_s": 1.5}
    with pytest.raises(SmokeGateError):
        apply_gate(current, current, realtime)
    artifact = tmp_path / "prev.json"
    artifact.write_text(json.dumps(current), encoding="utf-8")
    assert artifact.is_file()
