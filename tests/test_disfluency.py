"""Self-repair keeps the later span of the same slot."""

from nlp.disfluency import apply_repairs
from server.config import Settings


def test_tuesday_no_wednesday_keeps_wednesday() -> None:
    tokens = ["Tuesday", "no", "Wednesday"]
    tags = ["B-date", "O", "B-date"]
    spans, n = apply_repairs(tokens, tags, Settings())
    assert n == 1
    assert len(spans) == 1
    assert spans[0].text == "Wednesday"


def test_tuesday_no_morning_keeps_tuesday() -> None:
    tokens = ["Tuesday", "no", "the", "morning"]
    tags = ["B-date", "O", "O", "B-time"]
    spans, n = apply_repairs(tokens, tags, Settings())
    assert n == 0
    assert [span.slot for span in spans] == ["date", "time"]
    assert spans[0].text == "Tuesday"
