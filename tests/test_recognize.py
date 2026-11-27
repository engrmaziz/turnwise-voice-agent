"""Stub recognize stays the CI default; callers can inject a transcribe function."""

from pathlib import Path

from training.nlu.recognize import recognize_scripts, stub_asr


def test_stub_asr_inserts_uh() -> None:
    assert stub_asr("book tuesday") == "book uh tuesday"


def test_injected_transcribe(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts.jsonl"
    scripts.write_text(
        '{"script_id":"s1","intent":"faq","slots":{"faq_query":"hours"},'
        '"persona":"brief","disfluency":false,"text":"what are your hours"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "asr.jsonl"

    def transcribe(text: str) -> str:
        return text.upper()

    rows = recognize_scripts(scripts, out, transcribe=transcribe)
    assert len(rows) == 1
    assert rows[0].asr_text == "WHAT ARE YOUR HOURS"
    assert out.is_file()
