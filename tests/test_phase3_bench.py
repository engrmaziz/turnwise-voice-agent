"""Phase 3 compare JSON and ADR-006 never invent a backend from blocked rows."""

from pathlib import Path

from evals.bench.adr006 import choose_backend
from evals.bench.asr_compare import FIXTURES, measure_asr_compare
from evals.bench.entity_wer import measure_entity_wer
from evals.bench.phase3 import run_phase3_benches
from evals.bench.schema import BenchRow
from server.config import Settings


def test_compare_is_blocked_without_weights(settings: Settings, tmp_path: Path) -> None:
    missing = str(tmp_path / "missing.onnx")
    configured = settings.model_copy(
        update={
            "asr_zipformer_encoder_path": missing,
            "asr_zipformer_decoder_path": missing,
            "asr_zipformer_joiner_path": missing,
            "asr_zipformer_tokens_path": str(tmp_path / "missing.txt"),
            "tts_piper_onnx_path": missing,
        }
    )
    rows = measure_asr_compare(configured)
    assert len(FIXTURES) == 20
    assert all(row.status == "blocked" for row in rows)
    choice, reason = choose_backend(rows)
    assert choice == "blocked"
    assert "empty" in reason
    entity = measure_entity_wer(configured, supports_hotwords=False)
    on_row = next(row for row in entity if row.name.endswith("bias_on"))
    assert on_row.reason == "unsupported"
    run_phase3_benches(
        configured,
        results_dir=tmp_path,
        adr_path=tmp_path / "ADR-006-asr-backend.md",
        supports_hotwords=False,
    )
    assert (tmp_path / "phase3_asr_compare.json").is_file()
    assert "blocked" in (tmp_path / "ADR-006-asr-backend.md").read_text(encoding="utf-8")


def test_choose_backend_picks_zipformer_when_whisper_blocked() -> None:
    rows = [
        BenchRow(
            name="asr.compare.zipformer.finalize",
            status="ok",
            p50_ms=80.0,
            p95_ms=90.0,
        ),
        BenchRow(
            name="asr.compare.whisper_la2.finalize",
            status="blocked",
            reason="weights_unpinned",
        ),
    ]
    choice, reason = choose_backend(rows)
    assert choice == "zipformer"
    assert "80.0" in reason
