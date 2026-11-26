"""Golden rows need asr_text and BIO aligned to ASR tokens.

Slot F1 published in docs must use reviewed rows only. Teacher-agreement is
not slot F1.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nlp.nlu_features import tokenize
from training.nlu.schema import GoldenRow


def test_missing_asr_text_fails() -> None:
    with pytest.raises(ValidationError):
        GoldenRow(
            script_id="s1",
            spoken_clean="book tuesday",
            asr_text="",
            intent="book",
            bio_asr=["O"],
            reviewer="engrmaziz",
            reviewed_at="2026-11-26T00:00:00Z",
        )


def test_clean_text_only_tag_set_fails() -> None:
    """BIO length must match ASR tokens, not the clean script."""
    with pytest.raises(ValidationError, match="bio_asr"):
        GoldenRow(
            script_id="s1",
            spoken_clean="book tuesday",
            asr_text="book uh tuesday",
            intent="book",
            bio_asr=["O", "B-date"],
            reviewer="engrmaziz",
            reviewed_at="2026-11-26T00:00:00Z",
        )


def test_fixture_rows_are_reviewed() -> None:
    path = Path("training/nlu/golden_fixture.jsonl")
    if not path.is_file():
        pytest.skip("golden fixture not generated yet")
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        row = GoldenRow.model_validate_json(raw)
        assert row.reviewer
        assert row.asr_text
        assert len(row.bio_asr) == len(tokenize(row.asr_text))
