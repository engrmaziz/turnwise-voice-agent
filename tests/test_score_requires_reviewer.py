"""Scorer refuses unreviewed golden files."""

from pathlib import Path

import pytest

from evals.nlu.score import UnreviewedGoldenError, load_golden, score_file
from training.nlu.golden_sample import PROJECTION_REVIEWER
from training.nlu.schema import GoldenRow


def test_missing_reviewer_raises(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text(
        '{"script_id": "s1", "spoken_clean": "x", "asr_text": "x", "intent": "faq",'
        ' "bio_asr": ["O"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(UnreviewedGoldenError):
        load_golden(path)


def test_projection_reviewer_is_not_a_waveform_listen(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    row = GoldenRow(
        script_id="s1",
        spoken_clean="hours",
        asr_text="hours",
        intent="faq",
        bio_asr=["O"],
        reviewer=PROJECTION_REVIEWER,
        reviewed_at="2026-11-27T00:00:00Z",
    )
    path.write_text(row.model_dump_json() + "\n", encoding="utf-8")
    payload = score_file(path)
    assert payload["waveform_listen"] is False
    assert payload["reviewers"] == [PROJECTION_REVIEWER]
    assert payload["n"] == 1
