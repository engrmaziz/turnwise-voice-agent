"""When the Piper voice is on disk, the lock sha256 must match."""

import tomllib
from pathlib import Path

import pytest

from scripts.download_models import verify_file

_ONNX = Path("models/weights/piper/en_US-amy-low.onnx")
_JSON = Path("models/weights/piper/en_US-amy-low.onnx.json")


@pytest.mark.skipif(not _ONNX.is_file(), reason="piper onnx not on this checkout")
def test_on_disk_piper_onnx_matches_lock() -> None:
    payload = tomllib.loads(Path("models/lock.toml").read_text(encoding="utf-8"))
    models = payload.get("model")
    assert isinstance(models, list)
    row = next(
        item
        for item in models
        if isinstance(item, dict) and item.get("name") == "piper_en_US_amy_low_onnx"
    )
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_ONNX, expected)
    assert _ONNX.stat().st_size == 63_104_526


@pytest.mark.skipif(not _JSON.is_file(), reason="piper json not on this checkout")
def test_on_disk_piper_json_matches_lock() -> None:
    payload = tomllib.loads(Path("models/lock.toml").read_text(encoding="utf-8"))
    models = payload.get("model")
    assert isinstance(models, list)
    row = next(
        item
        for item in models
        if isinstance(item, dict) and item.get("name") == "piper_en_US_amy_low_json"
    )
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_JSON, expected)
    assert _JSON.stat().st_size == 4164
