"""Truncation JSONL: one positive and at least one incomplete prefix per sentence."""

from pathlib import Path

from training.turn.build_truncation import (
    generate_fixture_lines,
    load_fixtures,
    truncation_rows,
    write_fixtures,
    write_jsonl,
)


def test_each_complete_has_an_incomplete_prefix() -> None:
    sentences = [
        "I need to book with Dr. Avery Lang on Wednesday at two thirty",
        "The sun rose over the river at dawn",
    ]
    for sentence in sentences:
        rows = truncation_rows(sentence)
        completes = [row for row in rows if row["complete"] == 1]
        incompletes = [row for row in rows if row["complete"] == 0]
        assert len(completes) >= 1
        assert len(incompletes) >= 1


def test_wednesday_complete_on_date_incomplete_on_none() -> None:
    sentence = "Wednesday I would like to book with Dr. Avery Lang at two"
    rows = truncation_rows(sentence)
    weekday = [row for row in rows if row["text"] == "Wednesday"]
    assert {"text": "Wednesday", "slot": "date", "complete": 1, "source": "weekday"} in weekday
    assert {"text": "Wednesday", "slot": "none", "complete": 0, "source": "cut"} in weekday


def test_jsonl_validates(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures.txt"
    write_fixtures(fixtures, target=40)
    sentences = load_fixtures(fixtures)
    assert len(sentences) == 40
    out = tmp_path / "truncation.jsonl"
    count = write_jsonl(sentences, out)
    assert count >= 80
    assert out.is_file()
    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == count


def test_fixture_generator_reaches_two_thousand() -> None:
    lines = generate_fixture_lines(target=2000)
    assert len(lines) >= 2000
    assert len(set(lines)) == len(lines)
