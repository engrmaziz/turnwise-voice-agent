"""Run every probe, write JSON, markdown, and ADR-004."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from evals.bench.adr import render_adr
from evals.bench.asr import measure_asr
from evals.bench.fixture import fixture_license, fixture_text, prepare_fixture
from evals.bench.harness import write_report
from evals.bench.host import collect_host
from evals.bench.llm import measure_llm
from evals.bench.schema import BenchReport
from evals.bench.tts import measure_tts
from server.config import Settings


def run_suite(settings: Settings, *, command: list[str] | None = None) -> BenchReport:
    started = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results_dir = Path(settings.bench_results_dir)
    fixture_dir = results_dir / "fixtures"
    wav_path, audio_kind, speech = prepare_fixture(fixture_dir)
    json_path = results_dir / f"{started}.json"
    markdown_path = Path(settings.bench_markdown_path)
    adr_path = Path(settings.bench_adr_path)
    rows = [
        *measure_asr(settings, speech_wav=speech),
        *measure_llm(settings),
        *measure_tts(settings),
    ]
    report = BenchReport(
        started_utc=started,
        command=command if command is not None else list(sys.argv),
        host=collect_host(),
        warmup=settings.bench_warmup,
        samples=settings.bench_samples,
        fixture_text=fixture_text(),
        fixture_license=fixture_license(),
        fixture_audio=f"{audio_kind}:{wav_path.as_posix()}",
        rows=rows,
        json_path=json_path.as_posix(),
        markdown_path=markdown_path.as_posix(),
        adr_path=adr_path.as_posix(),
    )
    write_report(report, json_path=json_path, markdown_path=markdown_path)
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(render_adr(report), encoding="utf-8")
    return report
