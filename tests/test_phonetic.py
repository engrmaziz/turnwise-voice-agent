"""Title strip, margin tie, and a unique last-name hit."""

from nlp.phonetic import resolve_entity, strip_title
from server.config import Settings


def test_strips_dr() -> None:
    assert strip_title("Dr. Avery Lang") == "avery lang"
    assert strip_title("doctor Nia Okonkwo") == "nia okonkwo"


def test_tie_within_margin_returns_two_candidates() -> None:
    """Two roster rows that share a last name score equally; neither is written.

    Heard ``Khan`` versus ``Dr. Khan`` / ``Dr. Kahn`` is *not* a tie under the
    0.6/0.4 formula (1.0 vs 0.76). Same-last-name catalog rows are.
    """
    settings = Settings()
    result = resolve_entity("Khan", ["Dr. Ann Khan", "Dr. Bob Khan"], settings)
    assert result.entity_id is None
    assert "Dr. Ann Khan" in result.candidates
    assert "Dr. Bob Khan" in result.candidates


def test_lang_resolves_uniquely() -> None:
    settings = Settings()
    result = resolve_entity(
        "Lang",
        ["Dr. Avery Lang", "Dr. Nia Okonkwo", "Dr. Samir Qadir"],
        settings,
    )
    assert result.entity_id == "Dr. Avery Lang"
