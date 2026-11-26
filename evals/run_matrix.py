"""Virtual-clock matrix driver. JSON reports actual n, never a pretend 900."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.metrics import task_success
from evals.schema import ScenarioError, find_scenario, load_scenario, load_smoke_ids
from server.config import Settings


async def run_matrix(
    *,
    n: int,
    scenario_dir: Path,
    smoke_path: Path,
    out: Path,
    settings: Settings,
) -> dict[str, object]:
    ids = load_smoke_ids(smoke_path)
    virtual_ids = []
    for scenario_id in ids:
        scenario = load_scenario(find_scenario(scenario_dir, scenario_id))
        if scenario.clock == "virtual":
            virtual_ids.append(scenario_id)
    if not virtual_ids:
        raise ScenarioError("no virtual-clock scenarios")
    chosen = tuple(virtual_ids[index % len(virtual_ids)] for index in range(n))
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    judgements = []
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for scenario_id in chosen:
            path = find_scenario(scenario_dir, scenario_id)
            scenario = load_scenario(path)
            if scenario.clock != "virtual" and settings.eval_time_scale != 1.0:
                rows.append({"id": scenario.id, "skipped": "clock_mismatch"})
                continue
            db = tmp_path / f"matrix-{scenario.id}-{len(rows)}.sqlite"
            trace = await run_scripted(scenario, db=db, settings=settings)
            judged = judge(scenario, trace, settings=settings)
            judgements.append(judged)
            rows.append(
                {
                    "id": scenario.id,
                    "success": judged.success,
                    "reason": judged.reason,
                    "state": trace.state_id,
                }
            )
    elapsed = time.perf_counter() - started
    ran = [row for row in rows if "success" in row]
    payload: dict[str, object] = {
        "n": len(ran),
        "requested_n": n,
        "elapsed_s": elapsed,
        "time_scale": settings.eval_time_scale,
        "clock": "virtual",
        "task_success": task_success(judgements) if judgements else 0.0,
        "rows": rows,
        "estimator": "db_judge",
    }
    await asyncio.to_thread(_write_json, out, payload)
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase9_matrix.json"))
    args = parser.parse_args(argv)
    settings = default_eval_settings()
    n = args.n if args.n is not None else settings.eval_matrix_n
    if n < 1:
        raise ScenarioError("n must be >= 1")
    asyncio.run(
        run_matrix(
            n=n,
            scenario_dir=Path(settings.eval_scenario_dir),
            smoke_path=Path(settings.eval_scenario_dir) / "smoke.yaml",
            out=args.out,
            settings=settings,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
