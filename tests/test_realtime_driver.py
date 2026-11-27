"""Realtime PCM driver skips virtual clocks and records play-ack TTFA at scale 1."""

from pathlib import Path

from evals.harness import default_eval_settings
from evals.realtime_driver import run_pcm_sessions
from evals.run_realtime import run_realtime


def test_realtime_skips_virtual_clock(tmp_path: Path) -> None:
    settings = default_eval_settings()
    out = tmp_path / "realtime.json"
    payload = run_realtime(n=2, out=out, settings=settings)
    assert payload["status"] == "skipped"
    assert payload["reason"] == "eval_time_scale is virtual"
    assert payload["product_quote"] is False
    assert out.is_file()


async def test_pcm_driver_n1_play_ack(tmp_path: Path) -> None:
    settings = default_eval_settings().model_copy(
        update={
            "eval_time_scale": 1.0,
            "http_port": 0,
            "vad_onnx_path": str(tmp_path / "missing.onnx"),
            "turn_model_enabled": False,
        }
    )
    payload = await run_pcm_sessions(settings, n=1, pace_s=0.02)
    assert payload["product_quote"] is False
    assert payload["ttfa_path"] == "stub_play_ack"
    acked = payload["sessions_acked"]
    assert isinstance(acked, int)
    assert acked == 1
    samples = payload["ttfa_samples"]
    assert isinstance(samples, int)
    assert samples >= 1
    assert payload["ttfa_p95_s"] is not None
