"""Empty model dir still serves /health 200 with degraded flags."""

from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings


def test_health_200_with_empty_model_dir(tmp_path: Path, settings: Settings) -> None:
    empty = tmp_path / "weights"
    empty.mkdir()
    configured = settings.model_copy(
        update={
            "vad_onnx_path": str(empty / "missing.onnx"),
            "turn_onnx_path": str(empty / "turn.onnx"),
            "nlu_model_path": "",
            "emotion_model_path": "",
            "emotion_model_enabled": False,
            "asr_backend": "",
            "tts_backend": "",
        }
    )
    app = create_app(configured)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["degraded_llm"] is True
        assert body["degraded_tts"] is True
        assert body["degraded_asr"] is True
