"""Whisper path resolution does not invent a layout."""

from pathlib import Path

import pytest

from models.asr_whisper import resolve_whisper_dir, whisper_unavailable_reason
from server.config import Settings


def test_missing_whisper_dir_is_unpinned(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("models.asr_whisper.find_cached_whisper", lambda: None)
    configured = settings.model_copy(
        update={
            "asr_whisper_model_path": str(tmp_path / "missing"),
            "bench_whisper_model": "",
        }
    )
    reason = whisper_unavailable_reason(configured)
    assert reason in {"import_faster_whisper", "weights_unpinned"}
    if reason == "weights_unpinned":
        assert resolve_whisper_dir(configured) is None
