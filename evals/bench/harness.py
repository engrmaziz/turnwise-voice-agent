"""Warmup, samples, p50, p95. The clock is ``perf_counter``, not a model."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path

from evals.bench.schema import BenchReport, BenchRow, RowStatus
from models.protocols import Benchmarkable


def percentile(samples: list[float], pct: float) -> float:
    """Linear interpolation on a sorted copy. ``pct`` is 0-100."""
    if not samples:
        raise ValueError("percentile needs at least one sample")
    if not 0.0 <= pct <= 100.0:
        raise ValueError("pct must be in [0, 100]")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def busy_wait(seconds: float) -> None:
    """Spin until ``seconds`` of wall time elapse. ``time.sleep`` is too coarse on Windows."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        pass


def time_callable(
    fn: Callable[[], None],
    *,
    warmup: int,
    samples: int,
) -> tuple[float, float, list[float]]:
    """Return (p50_ms, p95_ms, sample_ms). Warmup is discarded."""
    if warmup < 0:
        raise ValueError("warmup must be >= 0")
    if samples < 1:
        raise ValueError("samples must be >= 1")
    for _ in range(warmup):
        fn()
    measured: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        fn()
        measured.append((time.perf_counter() - started) * 1000.0)
    return percentile(measured, 50.0), percentile(measured, 95.0), measured


def time_worker(
    worker: Benchmarkable,
    *,
    warmup: int,
    samples: int,
) -> tuple[str, float, float, list[float]]:
    p50, p95, measured = time_callable(worker.run_once, warmup=warmup, samples=samples)
    return worker.describe(), p50, p95, measured


def blocked_row(name: str, reason: str, *, version: str | None = None) -> BenchRow:
    return BenchRow(name=name, status="blocked", version=version, reason=reason)


def not_present_row(name: str, reason: str) -> BenchRow:
    return BenchRow(name=name, status="not_present", reason=reason)


def ok_row(
    name: str,
    *,
    version: str,
    p50_ms: float,
    p95_ms: float,
    extra: dict[str, object] | None = None,
) -> BenchRow:
    return BenchRow(
        name=name,
        status="ok",
        version=version,
        p50_ms=p50_ms,
        p95_ms=p95_ms,
        extra=extra or {},
    )


def cell_ms(row: BenchRow, value: float | None = None) -> str:
    """Human cell. Blocked and missing rows never render as 0."""
    sample = row.p50_ms if value is None else value
    if row.status != "ok" or sample is None:
        return row.status
    suffix = " tok/s" if row.extra.get("unit") == "tokens_per_second" else ""
    return f"{sample:.1f}{suffix}"


def render_markdown(report: BenchReport) -> str:
    lines = [
        "# Benchmarks",
        "",
        "Generated from the JSON sibling named in this file. Do not hand-edit numbers.",
        "",
        f"- Host: `{report.host.platform}`",
        f"- Python: `{report.host.python}`",
        f"- CPUs: {report.host.cpu_count}",
        f"- RAM GiB: {report.host.ram_gb if report.host.ram_gb is not None else 'unknown'}",
        f"- GPU (`nvidia-smi`): `{report.host.nvidia_status}`"
        + (f" `{report.host.nvidia_smi}`" if report.host.nvidia_smi else ""),
        f"- Command: `{' '.join(report.command)}`",
        f"- JSON: `{report.json_path}`",
        f"- Warmup {report.warmup}, samples {report.samples}",
        f"- Fixture text ({report.fixture_license}): {report.fixture_text}",
        f"- Fixture audio: {report.fixture_audio}",
        "",
        "| Name | Status | Version | p50 ms | p95 ms | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        version = row.version if row.version is not None else ""
        p50 = cell_ms(row, row.p50_ms)
        p95 = cell_ms(row, row.p95_ms)
        reason = row.reason or ""
        lines.append(f"| `{row.name}` | {row.status} | {version} | {p50} | {p95} | {reason} |")
    lines.append("")
    lines.append(
        "A numeric cell is valid only when Status is `ok`. "
        "`blocked` means the binary or weights were missing. "
        "`not_present` is reserved for a GPU row when `nvidia-smi` failed."
    )
    lines.append("")
    return "\n".join(lines)


def write_report(report: BenchReport, *, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def measured_ok(report: BenchReport, prefix: str) -> bool:
    return any(row.name.startswith(prefix) and row.status == "ok" for row in report.rows)


def row_status(report: BenchReport, name: str) -> RowStatus | None:
    for row in report.rows:
        if row.name == name:
            return row.status
    return None
