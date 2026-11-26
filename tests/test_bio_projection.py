"""BIO projection: insertions are O, deletions drop, phonetic subs keep the tag."""

from nlp.nlu_features import tokenize
from training.nlu.align_bio import bio_from_slots, project_bio


def test_insertion_is_o() -> None:
    clean = ["book", "tuesday"]
    tags = ["O", "B-date"]
    asr = ["book", "uh", "tuesday"]
    projected, low = project_bio(clean, tags, asr)
    assert projected == ["O", "O", "B-date"]
    assert low is False


def test_deletion_drops_clean_tag() -> None:
    clean = ["book", "with", "Lang"]
    tags = ["O", "O", "B-doctor"]
    asr = ["book", "Lang"]
    projected, _low = project_bio(clean, tags, asr)
    assert projected == ["O", "B-doctor"]


def test_phonetic_substitution_keeps_tag() -> None:
    clean = ["book", "Lang"]
    tags = ["O", "B-doctor"]
    asr = ["book", "Lan"]
    projected, low = project_bio(clean, tags, asr)
    assert projected == ["O", "B-doctor"]
    assert low is False


def test_unrelated_substitution_is_o_and_align_low() -> None:
    clean = ["book", "Lang"]
    tags = ["O", "B-doctor"]
    asr = ["book", "pizza"]
    projected, low = project_bio(clean, tags, asr)
    assert projected == ["O", "O"]
    assert low is True


def test_bio_from_slots_tags_doctor() -> None:
    text = "book with Dr. Avery Lang on Tuesday"
    tags = bio_from_slots(text, {"doctor": "Dr. Avery Lang", "date": "Tuesday"})
    tokens = tokenize(text)
    assert len(tags) == len(tokens)
    assert "B-doctor" in tags
    assert "B-date" in tags
