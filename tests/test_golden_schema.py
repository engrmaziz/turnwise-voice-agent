"""Golden rows need asr_text and BIO aligned to ASR tokens.

Slot F1 published in docs must use reviewed rows only. Teacher-agreement is
not slot F1.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nlp.nlu_features import tokenize
from nlp.nlu_vocab import INTENTS
from training.nlu.golden_sample import split_train_golden
from training.nlu.schema import AsrTrainRow, GoldenRow


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


def test_split_train_golden_is_disjoint() -> None:
    rows = [
        AsrTrainRow(
            script_id=f"s{index:04d}",
            spoken_clean="hours",
            asr_text="hours",
            intent=INTENTS[index % len(INTENTS)],
            bio_asr=["O"],
        )
        for index in range(32)
    ]
    train, golden = split_train_golden(rows, golden_n=24)
    assert len(golden) == 24
    assert len(train) == 8
    train_ids = {row.script_id for row in train}
    gold_ids = {row.script_id for row in golden}
    assert train_ids.isdisjoint(gold_ids)
    assert train_ids | gold_ids == {row.script_id for row in rows}
