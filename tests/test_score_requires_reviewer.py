"""Scorer refuses unreviewed golden files."""

from pathlib import Path

import pytest

from evals.nlu.score import UnreviewedGoldenError, load_golden


def test_missing_reviewer_raises(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text(
        '{"script_id": "s1", "spoken_clean": "x", "asr_text": "x", "intent": "faq",'
        ' "bio_asr": ["O"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(UnreviewedGoldenError):
        load_golden(path)
