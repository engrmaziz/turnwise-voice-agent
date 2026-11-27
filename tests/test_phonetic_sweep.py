"""Phonetic sweep stays untuned until 500 reviewed rows exist."""

from pathlib import Path

from evals.nlu.phonetic_sweep import sweep_or_untuned
from training.nlu.golden_sample import PROJECTION_REVIEWER
from training.nlu.schema import GoldenRow


def _row(script_id: str) -> GoldenRow:
    return GoldenRow(
        script_id=script_id,
        spoken_clean="hours",
        asr_text="hours",
        intent="faq",
        bio_asr=["O"],
        reviewer=PROJECTION_REVIEWER,
        reviewed_at="2026-11-27T00:00:00Z",
    )


def test_untuned_when_short(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text(_row("s1").model_dump_json() + "\n", encoding="utf-8")
    result = sweep_or_untuned(path, complete_n=500)
    assert result["status"] == "untuned"
    assert result["reason"] == "golden_incomplete"


def test_swept_when_n_met(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    lines = [_row(f"s{index}").model_dump_json() for index in range(2)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = sweep_or_untuned(path, complete_n=2)
    assert result["status"] == "swept"
    assert result["n"] == 2
    grid = result["grid"]
    assert isinstance(grid, list)
    assert len(grid) == 9
