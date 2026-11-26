"""Write Phase 3 compare JSON, entity-WER JSON, and ADR-006 from those rows."""

from __future__ import annotations

from pathlib import Path

from evals.bench.adr006 import render_adr006
from evals.bench.asr_compare import measure_asr_compare, write_compare_json
from evals.bench.entity_wer import measure_entity_wer, write_entity_json
from server.config import Settings


def run_phase3_benches(
    settings: Settings,
    *,
    results_dir: Path,
    adr_path: Path,
    supports_hotwords: bool = True,
) -> None:
    compare = measure_asr_compare(settings)
    entity = measure_entity_wer(settings, supports_hotwords=supports_hotwords)
    compare_path = results_dir / "phase3_asr_compare.json"
    entity_path = results_dir / "phase3_entity_wer.json"
    write_compare_json(compare, compare_path)
    write_entity_json(entity, entity_path)
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(
        render_adr006(compare, json_path=compare_path.as_posix()),
        encoding="utf-8",
    )
