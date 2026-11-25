"""Resample lives only at ingress."""

from pathlib import Path

_ALLOWED = frozenset({"format.py", "audio_in.py"})


def test_resample_imported_only_at_ingress() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in (root / "pipeline").rglob("*.py"):
        if path.name in _ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        if "resample_mono_pcm16" in text:
            offenders.append(str(path.relative_to(root)))
    asr = root / "pipeline" / "stages" / "asr.py"
    if asr.is_file() and "resample_mono_pcm16" in asr.read_text(encoding="utf-8"):
        offenders.append("pipeline/stages/asr.py")
    assert offenders == []
