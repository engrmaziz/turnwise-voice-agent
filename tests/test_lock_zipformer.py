"""When Zipformer weights are on disk, the lock sha256 must match."""

import tomllib
from pathlib import Path

import pytest

from scripts.download_models import verify_file

_DIR = Path("models/weights/zipformer")
_ENCODER = _DIR / "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
_DECODER = _DIR / "decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
_JOINER = _DIR / "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
_TOKENS = _DIR / "tokens.txt"
_BPE_MODEL = _DIR / "bpe.model"


def _row(name: str) -> dict[str, object]:
    payload = tomllib.loads(Path("models/lock.toml").read_text(encoding="utf-8"))
    models = payload.get("model")
    assert isinstance(models, list)
    return next(item for item in models if isinstance(item, dict) and item.get("name") == name)


@pytest.mark.skipif(not _ENCODER.is_file(), reason="zipformer encoder not on this checkout")
def test_on_disk_zipformer_encoder_matches_lock() -> None:
    row = _row("zipformer_en_2023_06_26_encoder_int8")
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_ENCODER, expected)
    assert _ENCODER.stat().st_size == 71_083_163


@pytest.mark.skipif(not _DECODER.is_file(), reason="zipformer decoder not on this checkout")
def test_on_disk_zipformer_decoder_matches_lock() -> None:
    row = _row("zipformer_en_2023_06_26_decoder_int8")
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_DECODER, expected)
    assert _DECODER.stat().st_size == 1_307_236


@pytest.mark.skipif(not _JOINER.is_file(), reason="zipformer joiner not on this checkout")
def test_on_disk_zipformer_joiner_matches_lock() -> None:
    row = _row("zipformer_en_2023_06_26_joiner_int8")
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_JOINER, expected)
    assert _JOINER.stat().st_size == 259_335


@pytest.mark.skipif(not _TOKENS.is_file(), reason="zipformer tokens not on this checkout")
def test_on_disk_zipformer_tokens_matches_lock() -> None:
    row = _row("zipformer_en_2023_06_26_tokens")
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_TOKENS, expected)
    assert _TOKENS.stat().st_size == 5048


@pytest.mark.skipif(not _BPE_MODEL.is_file(), reason="zipformer bpe.model not on this checkout")
def test_on_disk_zipformer_bpe_model_matches_lock() -> None:
    row = _row("zipformer_en_2023_06_26_bpe_model")
    expected = str(row.get("sha256") or "")
    assert len(expected) == 64
    verify_file(_BPE_MODEL, expected)
    assert _BPE_MODEL.stat().st_size == 244_865
