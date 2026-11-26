"""CI smoke gate. Slot F1 is not a gate until T5.4.4 publishes a number."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.harness import default_eval_settings, run_scripted
from evals.judge_db import judge
from evals.metrics import task_success
from evals.schema import find_scenario, load_scenario, load_smoke_ids

# STARTING POINT slack. Tightening needs a week of green runs.
SUCCESS_SLACK = 0.05
TTFA_P95_CAP = 1.2


class SmokeGateError(SystemExit):
    """Smoke task-success drop or realtime P95 over cap."""


async def run_smoke(*, scenario_dir: Path, smoke_path: Path) -> dict[str, object]:
    settings = default_eval_settings()
    ids = load_smoke_ids(smoke_path)
    rows: list[dict[str, object]] = []
    judgements = []
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for scenario_id in ids:
            scenario = load_scenario(find_scenario(scenario_dir, scenario_id))
            db = tmp_path / f"{scenario.id}.sqlite"
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
    payload: dict[str, object] = {
        "n": len(judgements),
        "task_success": task_success(judgements) if judgements else 0.0,
        "rows": rows,
        "slot_f1_gate": "forbidden_until_golden_published",
    }
    return payload


def apply_gate(
    current: Mapping[str, object],
    previous: Mapping[str, object] | None,
    realtime: Mapping[str, object] | None,
) -> None:
    if previous is not None and "task_success" in previous:
        prior = _as_float(previous["task_success"], "previous.task_success")
        now = _as_float(current["task_success"], "current.task_success")
        if now < prior - SUCCESS_SLACK:
            raise SmokeGateError(
                f"smoke task_success {now} dropped more than {SUCCESS_SLACK} from {prior}"
            )
    if realtime is None or realtime.get("status") == "skipped":
        return
    p95 = realtime.get("ttfa_p95_s")
    if p95 is None:
        return
    if _as_float(p95, "ttfa_p95_s") > TTFA_P95_CAP:
        raise SmokeGateError(f"realtime ttfa p95 {p95} above {TTFA_P95_CAP}")


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise SmokeGateError(f"{name} is not numeric")
    return float(value)


def main(argv: list[str] | None = None) -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("docs/results/smoke_artifact.json"))
    parser.add_argument(
        "--previous",
        type=Path,
        default=Path("docs/results/smoke_artifact.json"),
    )
    parser.add_argument(
        "--realtime",
        type=Path,
        default=Path("docs/results/phase9_realtime.json"),
    )
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args(argv)
    payload = asyncio.run(
        run_smoke(
            scenario_dir=Path("evals/scenarios"),
            smoke_path=Path("evals/scenarios/smoke.yaml"),
        )
    )
    previous = None
    if args.previous.is_file() and (
        args.previous.resolve() != args.artifact.resolve() or not args.write_only
    ):
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    realtime = None
    if args.realtime.is_file():
        realtime = json.loads(args.realtime.read_text(encoding="utf-8"))
    if not args.write_only:
        apply_gate(payload, previous, realtime)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
