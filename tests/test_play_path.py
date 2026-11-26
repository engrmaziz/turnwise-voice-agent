"""Play-ack path observes TTFA without inventing a product P50."""

from pathlib import Path

from prometheus_client import CollectorRegistry

from evals.harness import default_eval_settings
from evals.play_path import run_scripted_play
from evals.schema import load_scenario
from models.tts_pool import TtsPool
from pipeline.metrics import build_stage_metrics
from tests.support import histogram_count


async def test_scripted_book_observes_play_ack_ttfa(tmp_path: Path) -> None:
    settings = default_eval_settings()
    metrics = build_stage_metrics(CollectorRegistry())
    pool = TtsPool.stub(
        timeout_ms=settings.tts_timeout_ms,
        frame_bytes=settings.tts_pcm_bytes,
    )
    try:
        scenario = load_scenario(Path("evals/scenarios/smoke/book_avery.yaml"))
        trace = await run_scripted_play(
            scenario,
            db=tmp_path / "clinic.sqlite",
            settings=settings,
            metrics=metrics,
            pool=pool,
        )
    finally:
        pool.close()
    assert trace.state_id == "CLOSE"
    assert len(trace.appointments) == 1
    assert histogram_count(metrics.ttfa) >= 1.0
