"""Piper CPU pool: missing weights stay unavailable; real synth is skipped in CI."""

import importlib.util
from pathlib import Path

import pytest

from models.tts_pool import TtsJob, TtsPool, load_tts_pool
from server.config import Settings
from tests.conftest import Harness

_ONNX = Path("models/weights/piper/en_US-amy-low.onnx")
_JSON = Path("models/weights/piper/en_US-amy-low.onnx.json")


def _piper_ready() -> bool:
    return importlib.util.find_spec("piper") is not None and _ONNX.is_file()


def test_piper_missing_onnx_is_unavailable(tmp_path: Path, settings: Settings) -> None:
    configured = settings.model_copy(
        update={
            "tts_backend": "piper",
            "tts_piper_onnx_path": str(tmp_path / "missing.onnx"),
            "tts_piper_config_path": str(tmp_path / "missing.onnx.json"),
        }
    )
    pool = load_tts_pool(configured)
    assert pool.available is False
    assert pool.synth_sync is None


def test_piper_missing_config_is_unavailable(tmp_path: Path, settings: Settings) -> None:
    onnx = tmp_path / "en_US-amy-low.onnx"
    onnx.write_bytes(b"not-a-real-onnx")
    configured = settings.model_copy(
        update={
            "tts_backend": "piper",
            "tts_piper_onnx_path": str(onnx),
            "tts_piper_config_path": str(tmp_path / "missing.onnx.json"),
        }
    )
    pool = load_tts_pool(configured)
    assert pool.available is False


@pytest.mark.skipif(not _piper_ready(), reason="piper extra or voice missing")
async def test_piper_synth_is_nonzero_pcm16(harness: Harness) -> None:
    pool = TtsPool.piper(
        onnx_path=_ONNX,
        config_path=_JSON,
        timeout_ms=harness.settings.tts_timeout_ms,
        output_hz=harness.settings.ws_sample_rate_hz,
    )
    result = await pool.synthesize(
        TtsJob(
            session_id=harness.session.session_id,
            generation=harness.session.generation,
            text="hello there",
            voice="default",
            speed=1.0,
            first_chunk=True,
        ),
        live=lambda: harness.session.generation,
    )
    pool.close()
    assert result is not None
    assert len(result.pcm) >= harness.settings.tts_pcm_bytes
    assert len(result.pcm) % 2 == 0
    assert result.pcm != b"\x00" * len(result.pcm)
    assert result.latency_ms > 0.0
