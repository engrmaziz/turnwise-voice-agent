"""Concurrent scripted load. Knee is the largest N whose TTFA p95 meets 1200 ms.

Scripted NLU inject does not play-ack. A histogram with zero samples is a miss,
not a guessed p95. ADR-004 stays blocked; the JSON names the host and that fact.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.schema import find_scenario, load_scenario
from pipeline.metrics import StageMetrics
from server.config import Settings

TTFA_P95_CAP = 1.2
ADR004_TIER = "blocked"


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
) -> dict[str, object]:
    scenario = load_scenario(find_scenario(scenario_dir, scenario_id))
    started = time.perf_counter()
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tasks = [
            run_scripted(scenario, db=tmp_path / f"load-{n}-{index}.sqlite", settings=settings)
            for index in range(n)
        ]
        traces = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - started
    successes = sum(1 for trace in traces if judge(scenario, trace, settings=settings).success)
    payload: dict[str, object] = {
        "n": n,
        "scenario_id": scenario_id,
        "elapsed_s": elapsed,
        "task_success": successes / n if n else 0.0,
        "ttfa_samples": 0,
        "ttfa_p95_s": None,
        "status": "miss",
        "reason": "no_play_ack_samples",
        "platform": platform.platform(),
        "adr004_tier": ADR004_TIER,
        "time_scale": settings.eval_time_scale,
        "gpu": "no_gpu_smi_on_event_loop",
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
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    misses = 0
    knee = 0
    for n in range(1, n_max + 1):
        row = await run_one_n(
            n=n,
            scenario_id=scenario_id,
            scenario_dir=scenario_dir,
            settings=settings,
            out=out_dir / f"load_n{n}.json",
        )
        rows.append(row)
        p95_raw = row["ttfa_p95_s"]
        samples_raw = row["ttfa_samples"]
        samples = samples_raw if isinstance(samples_raw, int) else 0
        p95 = p95_raw if isinstance(p95_raw, int | float) else None
        miss = samples <= 0 or p95 is None or float(p95) > TTFA_P95_CAP
        if miss:
            misses += 1
        else:
            misses = 0
            knee = n
        if misses >= 2:
            break
    summary: dict[str, object] = {
        "knee": knee,
        "n_max_ran": rows[-1]["n"] if rows else 0,
        "requested_n_max": n_max,
        "platform": platform.platform(),
        "adr004_tier": ADR004_TIER,
        "ttfa_p95_cap_s": TTFA_P95_CAP,
        "rows": rows,
        "reason": "n=0 failed at 1" if knee == 0 else "largest_n_at_or_under_cap",
    }
    await asyncio.to_thread(_write_json, out_dir / "phase10_load.json", summary)
    return summary


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def render_markdown(summary: dict[str, object]) -> str:
    rows = summary.get("rows")
    lines = [
        "# Phase 10 load",
        "",
        "Numbers are copied from JSON. TTFA p95 is not invented when play-ack count is 0.",
        "",
        f"- `platform`: {summary.get('platform')}",
        f"- `adr004_tier`: {summary.get('adr004_tier')}",
        f"- `knee`: {summary.get('knee')}",
        f"- `reason`: {summary.get('reason')}",
        "",
        "| n | ttfa_samples | ttfa_p95_s | status | elapsed_s |",
        "|---|---|---|---|---|",
    ]
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('n')} | {row.get('ttfa_samples')} | {row.get('ttfa_p95_s')} |"
                f" {row.get('status')} | {row.get('elapsed_s')} |"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/results"))
    parser.add_argument("--scenario", default="book_avery")
    args = parser.parse_args(argv)
    settings = default_eval_settings()
    n_max = args.n if args.n is not None else settings.load_n_max
    summary = asyncio.run(
        run_until_knee(
            n_max=n_max,
            scenario_id=args.scenario,
            scenario_dir=Path(settings.eval_scenario_dir),
            settings=settings,
            out_dir=args.out_dir,
        )
    )
    (args.out_dir / "phase10_load.md").write_text(render_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
