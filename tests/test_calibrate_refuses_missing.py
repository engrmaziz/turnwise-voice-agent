"""Calibration refuses to invent ECE bins when labels were not collected."""

from pathlib import Path

import pytest

from evals.emotion.calibrate import CalibrationMissingError, load_call_like, main


def test_repo_call_like_is_not_collected() -> None:
    with pytest.raises(CalibrationMissingError, match="not_collected"):
        load_call_like(Path("training/emotion/call_like.jsonl"))


def test_main_exits_2() -> None:
    assert main([]) == 2


def test_partial_labels_still_refused(tmp_path: Path) -> None:
    path = tmp_path / "call_like.jsonl"
    path.write_text('{"label": "calm", "source": "operator"}\n', encoding="utf-8")
    with pytest.raises(CalibrationMissingError, match="30"):
        load_call_like(path)
