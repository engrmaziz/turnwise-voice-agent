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
                "llm_backend": "",
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


def test_health_200_when_zipformer_encoder_missing(tmp_path: Path, settings: Settings) -> None:
    empty = tmp_path / "weights"
    empty.mkdir()
    configured = settings.model_copy(
        update={
            "asr_backend": "zipformer",
            "asr_zipformer_encoder_path": str(empty / "missing.onnx"),
            "tts_backend": "",
        }
    )
    app = create_app(configured)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["degraded_asr"] is True


def test_health_200_when_piper_onnx_missing(tmp_path: Path, settings: Settings) -> None:
    empty = tmp_path / "weights"
    empty.mkdir()
    configured = settings.model_copy(
        update={
            "tts_backend": "piper",
            "tts_piper_onnx_path": str(empty / "en_US-amy-low.onnx"),
            "tts_piper_config_path": str(empty / "en_US-amy-low.onnx.json"),
            "asr_backend": "",
        }
    )
    app = create_app(configured)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["degraded_tts"] is True


def test_health_200_when_ollama_host_down(settings: Settings) -> None:
    configured = settings.model_copy(
        update={
            "llm_backend": "ollama",
            "llm_ollama_host": "http://127.0.0.1:1",
            "llm_timeout_ms": 200,
        }
    )
    app = create_app(configured)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["degraded_llm"] is True
