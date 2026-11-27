"""Calibration refuses to invent ECE bins when labels were not collected."""

import json
from pathlib import Path

import pytest

from evals.emotion.calibrate import (
    CalibrationMissingError,
    expected_calibration_error,
    load_call_like,
    main,
    scored_pairs,
    write_reliability_csv,
)


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


def test_labels_without_scores_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "call_like.jsonl"
    lines = [json.dumps({"label": "calm", "source": "operator"}) + "\n" for _ in range(30)]
    path.write_text("".join(lines), encoding="utf-8")
    rows = load_call_like(path)
    with pytest.raises(CalibrationMissingError, match="scored"):
        scored_pairs(rows)


def test_ece_writer_from_scored_rows(tmp_path: Path) -> None:
    rows = [{"label": "calm", "score": 0.1} for _ in range(15)]
    rows.extend({"label": "distressed", "score": 0.9} for _ in range(15))
    pairs = scored_pairs(rows)
    ece, table = expected_calibration_error(pairs)
    assert 0.0 <= ece <= 1.0
    out = tmp_path / "phase8_calibration.csv"
    write_reliability_csv(out, ece=ece, table=table)
    text = out.read_text(encoding="utf-8")
    assert "ece" in text
    assert str(ece) in text or "0." in text
