"""One concurrent scripted session writes JSON that does not pretend to be 900."""

from pathlib import Path

import pytest

from evals.harness import default_eval_settings
from evals.load import LoadError, llm_for_load, pool_for_load, run_one_n, tts_path_label
from models.tts_pool import TtsPool


async def test_load_n1_reports_actual_n_and_stub_play_ack(tmp_path: Path) -> None:
    out = tmp_path / "load_n1.json"
    payload = await run_one_n(
        n=1,
        scenario_id="book_avery",
        scenario_dir=Path("evals/scenarios"),
        settings=default_eval_settings(),
        out=out,
    )
    assert payload["n"] == 1
    samples = payload["ttfa_samples"]
    assert isinstance(samples, int)
    assert samples >= 1
    assert payload["ttfa_p95_s"] is not None
    assert payload["ttfa_path"] == "stub_play_ack"
    assert payload["product_quote"] is False
    assert payload["adr004_tier"] == "blocked"
    assert payload["status"] in {"hit", "miss"}
    assert "platform" in payload
    assert out.is_file()
    assert payload["tts_backend"] == "stub"
    assert payload["sessions_acked"] == 1


def test_tts_path_label_names_stub_and_piper() -> None:
    stub = TtsPool.stub(timeout_ms=50, frame_bytes=640)
    stub.close()
    assert tts_path_label(stub) == "stub_play_ack"
    named = TtsPool.unavailable(timeout_ms=50)
    named.model_name = "piper:en_US-amy-low.onnx"
    assert tts_path_label(named) == "piper_play_ack"


def test_piper_load_without_onnx_raises(tmp_path: Path) -> None:
    settings = default_eval_settings().model_copy(
        update={
            "tts_backend": "piper",
            "tts_piper_onnx_path": str(tmp_path / "missing.onnx"),
        }
    )
    with pytest.raises(LoadError, match="unavailable"):
        pool_for_load(settings)


def test_llm_for_load_empty_is_unavailable() -> None:
    client = llm_for_load(default_eval_settings())
    assert client.available is False
    client.close()


def test_llm_for_load_unknown_raises() -> None:
    settings = default_eval_settings().model_copy(update={"llm_backend": "not-a-backend"})
    with pytest.raises(LoadError, match="unknown"):
        llm_for_load(settings)
