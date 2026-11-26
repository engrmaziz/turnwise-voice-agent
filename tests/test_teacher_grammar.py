"""Teacher output is schema-constrained. Grammar reject drops the row."""

from pathlib import Path

from training.nlu.teach import apply_teacher_file, parse_teacher_json


def test_unknown_slot_key_is_dropped() -> None:
    assert parse_teacher_json('{"intent": "book", "slots": {"favorite_color": "x"}}') is None


def test_valid_teacher_json_parses() -> None:
    label = parse_teacher_json('{"intent": "book", "slots": {"date": "Tuesday"}}')
    assert label is not None
    assert label.intent == "book"


def test_grammar_reject_drops_row(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    rows.write_text(
        '{"script_id": "s1", "spoken_clean": "book tuesday", "asr_text": "book tuesday",'
        ' "intent": "book", "bio_asr": ["O", "B-date"], "align_low": false}\n',
        encoding="utf-8",
    )
    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        '{"script_id": "s1", "teacher_json": "not-json"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "kept.jsonl"
    dropped = apply_teacher_file(rows, labels, out)
    assert dropped == 1
    assert out.read_text(encoding="utf-8").strip() == ""
