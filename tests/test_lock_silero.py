"""When Silero weights are on disk, the lock sha256 must match."""

import tomllib
from pathlib import Path

import pytest

from scripts.download_models import verify_file

_WEIGHTS = Path("models/weights/silero_vad.onnx")


@pytest.mark.skipif(not _WEIGHTS.is_file(), reason="silero weights not on this checkout")
def test_on_disk_silero_matches_lock() -> None:
    payload = tomllib.loads(Path("models/lock.toml").read_text(encoding="utf-8"))
    models = payload.get("model")
    assert isinstance(models, list)
    silero = next(
        row for row in models if isinstance(row, dict) and row.get("name") == "silero_vad"
    )
    expected = str(silero.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_WEIGHTS, expected)
    assert _WEIGHTS.stat().st_size == 2_204_103
