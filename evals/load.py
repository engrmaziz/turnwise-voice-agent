"""Concurrent scripted load with play-ack.

TTFA samples come from AudioOutHandler.note_play_ack after a synthetic TURN_END.
That is not a product SLO quote (ADR-012). ADR-004 stays blocked. Histogram p95
is a Prometheus bucket upper bound, not an interpolated millisecond.

Default settings keep the silence stub so CI stays weight-free. Pass
``--tts-backend piper`` after ``uv sync --extra tts`` and
``python scripts/download_models.py`` to measure a synthesizer column.
``--llm-backend ollama`` adds strategy B (batch 1) and C (batch 4) on the Piper path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from prometheus_client import CollectorRegistry

from evals.harness import default_eval_settings
from evals.judge_db import judge
from evals.play_path import run_scripted_play
from evals.schema import find_scenario, load_scenario
from models.llm_client import LlmClient
from models.tts_pool import TtsPool, load_tts_pool
from pipeline.metrics import StageMetrics, build_stage_metrics
from server.config import Settings

TTFA_P95_CAP = 1.2
ADR004_TIER = "blocked"


class LoadError(RuntimeError):
    """Load driver cannot start with the requested TTS backend."""


def tts_path_label(pool: TtsPool) -> str:
    name = pool.model_name
    if name == "stub":
        return "stub_play_ack"
    if name.startswith("piper"):
        return "piper_play_ack"
    return f"{name}_play_ack"


def pool_for_load(settings: Settings) -> TtsPool:
    pool = load_tts_pool(settings)
    backend = settings.tts_backend.strip()
    if backend in {"", "stub"}:
        return pool
    if not pool.available:
        raise LoadError(f"tts backend {backend} is unavailable")
    return pool


def llm_for_load(settings: Settings) -> LlmClient:
    backend = settings.llm_backend.strip()
    if backend == "":
        return LlmClient.unavailable(
            timeout_ms=settings.llm_timeout_ms,
            max_batch=settings.llm_max_batch,
        )
    if backend != "ollama":
        raise LoadError(f"unknown llm_backend {backend}")
    try:
        return LlmClient.ollama(
            host=settings.llm_ollama_host,
            model=settings.llm_ollama_model,
            timeout_ms=settings.llm_timeout_ms,
            max_batch=settings.llm_max_batch,
        )
    except (OSError, FileNotFoundError, ValueError, RuntimeError) as exc:
        raise LoadError(f"llm backend {backend} is unavailable: {exc}") from exc


def histogram_p95(metrics: StageMetrics) -> tuple[int, float | None]:
    """Read count and an in-process p95 from the TTFA histogram. Empty is not a number."""
    count = 0
    buckets: list[tuple[float, float]] = []
    for family in metrics.ttfa.collect():
        for sample in family.samples:
            if sample.name.endswith("_count"):
                count = int(sample.value)
            elif sample.name.endswith("_bucket"):
                le = sample.labels.get("le")
                if le is None or le == "+Inf":
                    continue
                buckets.append((float(le), float(sample.value)))
    if count <= 0 or not buckets:
        return count, None
    buckets.sort()
    target = 0.95 * count
    for bound, cumulative in buckets:
        if cumulative >= target:
            return count, bound
    return count, buckets[-1][0]


async def run_one_n(
    *,
    n: int,
    scenario_id: str,
    scenario_dir: Path,
    settings: Settings,
    out: Path,
    pool: TtsPool | None = None,
    llm: LlmClient | None = None,
) -> dict[str, object]:
    scenario = load_scenario(find_scenario(scenario_dir, scenario_id))
    metrics = build_stage_metrics(CollectorRegistry())
    owned = pool is None
    engine = pool if pool is not None else pool_for_load(settings)
    path = tts_path_label(engine)
    started = time.perf_counter()
    try:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tasks = [
                run_scripted_play(
                    scenario,
                    db=tmp_path / f"load-{n}-{index}.sqlite",
                    settings=settings,
                    metrics=metrics,
                    pool=engine,
                    llm=llm,
                )
                for index in range(n)
            ]
            traces = await asyncio.gather(*tasks)
    finally:
        if owned:
            engine.close()
    elapsed = time.perf_counter() - started
    successes = sum(1 for trace in traces if judge(scenario, trace, settings=settings).success)
    acked = sum(1 for trace in traces if trace.play_emitted > 0)
    samples, p95 = histogram_p95(metrics)
    miss = samples <= 0 or p95 is None or float(p95) > TTFA_P95_CAP or acked < n
    payload: dict[str, object] = {
        "n": n,
        "scenario_id": scenario_id,
        "elapsed_s": elapsed,
        "task_success": successes / n if n else 0.0,
        "ttfa_samples": samples,
        "sessions_acked": acked,
        "ttfa_p95_s": p95,
        "ttfa_p95_source": "histogram_bucket",
        "ttfa_path": path,
        "product_quote": False,
        "status": "miss" if miss else "hit",
        "reason": _row_reason(samples, miss, acked=acked, n=n),
        "platform": platform.platform(),
        "adr004_tier": ADR004_TIER,
        "time_scale": settings.eval_time_scale,
        "gpu": "no_gpu_smi_on_event_loop",
        "tts_backend": engine.model_name,
        "llm_backend": settings.llm_backend.strip() or "unavailable",
        "llm_max_batch": settings.llm_max_batch,
    }
    await asyncio.to_thread(_write_json, out, payload)
    return payload


async def run_until_knee(
    *,
    n_max: int,
    scenario_id: str,
    scenario_dir: Path,
    settings: Settings,
    out_dir: Path,
    prefix: str,
) -> dict[str, object]:
    pool = pool_for_load(settings)
    llm = llm_for_load(settings)
    path = tts_path_label(pool)
    rows: list[dict[str, object]] = []
    misses = 0
    knee = 0
    try:
        for n in range(1, n_max + 1):
            row = await run_one_n(
                n=n,
                scenario_id=scenario_id,
                scenario_dir=scenario_dir,
                settings=settings,
                out=out_dir / f"{prefix}_n{n}.json",
                pool=pool,
                llm=llm,
            )
            rows.append(row)
            p95_raw = row["ttfa_p95_s"]
            samples_raw = row["ttfa_samples"]
            acked_raw = row["sessions_acked"]
            samples = samples_raw if isinstance(samples_raw, int) else 0
            acked = acked_raw if isinstance(acked_raw, int) else 0
            p95 = p95_raw if isinstance(p95_raw, int | float) else None
            n_val = row["n"]
            n_i = n_val if isinstance(n_val, int) else 0
            miss = samples <= 0 or p95 is None or float(p95) > TTFA_P95_CAP or acked < n_i
            if miss:
                misses += 1
            else:
                misses = 0
                knee = n
            if misses >= 2:
                break
    finally:
        pool.close()
        llm.close()
    summary: dict[str, object] = {
        "knee": knee,
        "n_max_ran": rows[-1]["n"] if rows else 0,
        "requested_n_max": n_max,
        "platform": platform.platform(),
        "adr004_tier": ADR004_TIER,
        "ttfa_p95_cap_s": TTFA_P95_CAP,
        "ttfa_path": path,
        "product_quote": False,
        "tts_backend": pool.model_name,
        "llm_backend": settings.llm_backend.strip() or "unavailable",
        "llm_max_batch": settings.llm_max_batch,
        "rows": rows,
        "reason": "n=0 failed at 1" if knee == 0 else "largest_n_at_or_under_cap",
        "contention": _contention(path, knee, rows),
    }
    await asyncio.to_thread(_write_json, out_dir / f"{prefix}.json", summary)
    return summary


def _knee_p95(rows: list[dict[str, object]], knee: int) -> float | None:
    for row in rows:
        if row.get("n") != knee:
            continue
        raw = row.get("ttfa_p95_s")
        if isinstance(raw, int | float):
            return float(raw)
        return None
    return None


def _strategy_column(
    name: str,
    *,
    summary: dict[str, object] | None = None,
    knee: int | None = None,
    p95: float | None = None,
    blocked: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    if blocked is not None:
        payload: dict[str, object] = {"name": name, "status": "blocked", "reason": blocked}
        if extra:
            payload.update(extra)
        return payload
    if summary is not None:
        raw_knee = summary.get("knee")
        knee_i = raw_knee if isinstance(raw_knee, int) else 0
        rows = summary.get("rows")
        row_list = rows if isinstance(rows, list) else []
        typed_rows = [row for row in row_list if isinstance(row, dict)]
        p95 = _knee_p95(typed_rows, knee_i)
        if p95 is None:
            p95 = _knee_p95(typed_rows, 1)
        payload = {
            "name": name,
            "status": "ok",
            "knee": knee_i,
            "ttfa_p95_s": p95,
            "llm_max_batch": summary.get("llm_max_batch"),
            "llm_backend": summary.get("llm_backend"),
        }
        if extra:
            payload.update(extra)
        return payload
    payload = {
        "name": name,
        "status": "ok",
        "knee": knee,
        "ttfa_p95_s": p95,
    }
    if extra:
        payload.update(extra)
    return payload


def _pick_contention(
    a: dict[str, object],
    b: dict[str, object],
    c: dict[str, object],
) -> tuple[str, str]:
    scored: list[tuple[str, float]] = []
    for label, item in (("A", a), ("B", b), ("C", c)):
        if item.get("status") != "ok":
            continue
        raw = item.get("ttfa_p95_s")
        if isinstance(raw, int | float):
            scored.append((label, float(raw)))
    if not scored:
        return "blocked", "no synthesizer p95 column"
    winner = min(scored, key=lambda pair: pair[1])
    return winner[0], f"lowest knee histogram p95 is {winner[0]} at {winner[1]}s"


def _contention(
    path: str,
    knee: int,
    rows: list[dict[str, object]],
    *,
    strategy_b: dict[str, object] | None = None,
    strategy_c: dict[str, object] | None = None,
) -> dict[str, object]:
    """A is CPU Piper. B/C are live-LLM columns when those knees were measured."""
    if path != "piper_play_ack":
        return {
            "pick": "blocked",
            "reason": "silence-stub play-ack is not a synthesizer p95",
            "strategy_a": {"name": "cpu_piper", "status": "not_run"},
            "strategy_b": strategy_b
            or {
                "name": "llm_speaking_priority",
                "status": "blocked",
                "reason": "llm_unavailable",
            },
            "strategy_c": strategy_c
            or {
                "name": "llm_max_batch_4",
                "status": "blocked",
                "reason": "llm_unavailable",
            },
        }
    column_a = _strategy_column(
        "cpu_piper",
        knee=knee,
        p95=_knee_p95(rows, knee),
        extra={"llm_backend": "unavailable", "llm_max_batch": 1},
    )
    column_b = strategy_b or {
        "name": "llm_speaking_priority",
        "status": "blocked",
        "reason": "llm_unavailable",
    }
    column_c = strategy_c or {
        "name": "llm_max_batch_4",
        "status": "blocked",
        "reason": "llm_unavailable",
    }
    pick, reason = _pick_contention(column_a, column_b, column_c)
    return {
        "pick": pick,
        "reason": reason,
        "strategy_a": column_a,
        "strategy_b": column_b,
        "strategy_c": column_c,
        "product_quote": False,
    }


def _row_reason(samples: int, miss: bool, *, acked: int, n: int) -> str:
    if samples <= 0:
        return "no_play_ack_samples"
    if acked < n:
        return "sessions_without_play_ack"
    if miss:
        return "over_cap"
    return "at_or_under_cap"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def render_markdown(summary: dict[str, object]) -> str:
    rows = summary.get("rows")
    path = str(summary.get("ttfa_path"))
    lines = [
        "# Phase 10 load",
        "",
        f"TTFA is `{path}`. It is not a product SLO quote (ADR-012).",
        "p95 is a Prometheus histogram bucket upper bound. ADR-004 stays blocked.",
        "",
        f"- `platform`: {summary.get('platform')}",
        f"- `adr004_tier`: {summary.get('adr004_tier')}",
        f"- `knee`: {summary.get('knee')}",
        f"- `reason`: {summary.get('reason')}",
        f"- `ttfa_path`: {summary.get('ttfa_path')}",
        f"- `product_quote`: {summary.get('product_quote')}",
        f"- `tts_backend`: {summary.get('tts_backend')}",
        f"- `llm_backend`: {summary.get('llm_backend')}",
        f"- `llm_max_batch`: {summary.get('llm_max_batch')}",
        "",
        "| n | sessions_acked | ttfa_samples | ttfa_p95_s | status | elapsed_s |",
        "|---|---|---|---|---|---|",
    ]
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('n')} | {row.get('sessions_acked')} | {row.get('ttfa_samples')} |"
                f" {row.get('ttfa_p95_s')} | {row.get('status')} | {row.get('elapsed_s')} |"
            )
    lines.append("")
    lines.append("## Contention (ADR-013)")
    lines.append("")
    contention = summary.get("contention")
    if isinstance(contention, dict):
        lines.append(f"- pick: `{contention.get('pick')}`")
        lines.append(f"- reason: {contention.get('reason')}")
        for key in ("strategy_a", "strategy_b", "strategy_c"):
            item = contention.get(key)
            if isinstance(item, dict):
                extra = ""
                if item.get("ttfa_p95_s") is not None:
                    extra = f", p95={item.get('ttfa_p95_s')}s knee={item.get('knee')}"
                lines.append(
                    f"- `{item.get('name')}`: {item.get('status')}"
                    + (f" ({item.get('reason')})" if item.get("reason") else extra)
                )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/results"))
    parser.add_argument("--scenario", default="book_avery")
    parser.add_argument(
        "--tts-backend",
        default="",
        help="Empty keeps the silence stub. piper requires the extra and locked ONNX.",
    )
    parser.add_argument(
        "--llm-backend",
        default="",
        help="Empty keeps LlmClient.unavailable. ollama runs B (batch 1) and C (batch 4).",
    )
    args = parser.parse_args(argv)
    settings = default_eval_settings()
    backend = str(args.tts_backend).strip()
    llm_backend = str(args.llm_backend).strip()
    updates: dict[str, object] = {}
    if backend:
        updates["tts_backend"] = backend
    if updates:
        settings = settings.model_copy(update=updates)
    prefix = "phase10_load_piper" if backend == "piper" else "phase10_load"
    n_max = args.n if args.n is not None else settings.load_n_max
    try:
        summary = asyncio.run(
            _run_cli(
                n_max=n_max,
                scenario_id=args.scenario,
                settings=settings,
                out_dir=args.out_dir,
                prefix=prefix,
                llm_backend=llm_backend,
            )
        )
    except LoadError as exc:
        raise SystemExit(str(exc)) from exc
    (args.out_dir / f"{prefix}.md").write_text(render_markdown(summary), encoding="utf-8")
    return 0


async def _run_cli(
    *,
    n_max: int,
    scenario_id: str,
    settings: Settings,
    out_dir: Path,
    prefix: str,
    llm_backend: str,
) -> dict[str, object]:
    scenario_dir = Path(settings.eval_scenario_dir)
    summary = await run_until_knee(
        n_max=n_max,
        scenario_id=scenario_id,
        scenario_dir=scenario_dir,
        settings=settings,
        out_dir=out_dir,
        prefix=prefix,
    )
    if llm_backend == "" or str(summary.get("ttfa_path")) != "piper_play_ack":
        return summary
    column_b = await run_until_knee(
        n_max=n_max,
        scenario_id=scenario_id,
        scenario_dir=scenario_dir,
        settings=settings.model_copy(update={"llm_backend": llm_backend, "llm_max_batch": 1}),
        out_dir=out_dir,
        prefix=f"{prefix}_b",
    )
    column_c = await run_until_knee(
        n_max=n_max,
        scenario_id=scenario_id,
        scenario_dir=scenario_dir,
        settings=settings.model_copy(update={"llm_backend": llm_backend, "llm_max_batch": 4}),
        out_dir=out_dir,
        prefix=f"{prefix}_c",
    )
    rows = summary.get("rows")
    typed_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    knee_raw = summary.get("knee")
    knee_i = knee_raw if isinstance(knee_raw, int) else 0
    summary["contention"] = _contention(
        str(summary.get("ttfa_path")),
        knee_i,
        typed_rows,
        strategy_b=_strategy_column("llm_speaking_priority", summary=column_b),
        strategy_c=_strategy_column("llm_max_batch_4", summary=column_c),
    )
    summary["llm_columns"] = {"b": column_b, "c": column_c}
    await asyncio.to_thread(_write_json, out_dir / f"{prefix}.json", summary)
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
