"""Health and metrics routes. TTFA histograms exist and have no samples."""

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings


def test_health_and_empty_ttfa_histogram(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "text/html" in home.headers["content-type"]
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "turnwise-test"}
        body = client.get("/metrics").text
    assert "turnwise_stage_latency_seconds" in body
    assert "turnwise_queue_depth" in body
    assert "turnwise_events_dropped_stale_total" in body
    assert "turnwise_stage_errors_total" in body
    assert "turnwise_backpressure_timeouts_total" in body
    assert "turnwise_barge_in_total" in body
    assert "turnwise_ttfa_seconds" in body
    assert "turnwise_ttfa_content_seconds" in body
    assert "turnwise_ws_frames_total" in body
    assert "turnwise_ws_rejects_total" in body
    assert "turnwise_audio_resample_seconds" in body
    assert "turnwise_vad_prob" in body
    assert "turnwise_audio_dead_total" in body
    assert "turnwise_asr_finalize_seconds" in body
    assert "turnwise_itn_seconds" in body
    assert "turnwise_temporal_seconds" in body
    assert "turnwise_endpoint_decisions_total" in body
    assert "turnwise_endpoint_silence_ms" in body
    assert "turnwise_turn_model_seconds" in body
    assert "turnwise_backchannel_ignored_total" in body
    assert "turnwise_cancel_latency_seconds" in body
    assert "turnwise_false_barge_in_total" in body
    assert "turnwise_missed_barge_in_total" in body
    assert "turnwise_ttfa_seconds_count 0.0" in body
    assert "turnwise_ttfa_content_seconds_count 0.0" in body


def test_metrics_route_can_be_disabled(settings: Settings) -> None:
    disabled = settings.model_copy(update={"metrics_enabled": False})
    app = create_app(disabled)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 404
