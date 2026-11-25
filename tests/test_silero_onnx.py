"""Load the real Silero ONNX when the download script has run."""

from pathlib import Path

import pytest

from models.vad_pool import VadPool

_ONNX = Path("models/weights/silero_vad.onnx")


@pytest.mark.skipif(not _ONNX.is_file(), reason="silero onnx not downloaded")
def test_silero_loads_and_names_the_file() -> None:
    pool = VadPool.load(_ONNX, timeout_ms=500, window_samples=512, sample_rate_hz=16000)
    assert pool.available is True
    assert pool.model_name == "silero_vad.onnx"
    state = pool.new_state()
    assert state is not None
    pool.close()
