"""Write docs/results/phase9.md from JSON. Every number has a key."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(
    matrix: dict[str, object],
    realtime: dict[str, object],
    ablations: dict[str, object],
    smoke: dict[str, object] | None = None,
) -> str:
    n = matrix.get("n")
    requested = matrix.get("requested_n")
    elapsed = matrix.get("elapsed_s")
    success = matrix.get("task_success")
    scale = matrix.get("time_scale")
    clock = matrix.get("clock")
    rt_status = realtime.get("status", "missing")
    rt_n = realtime.get("n", 0)
    rt_reason = realtime.get("reason", "")
    lines = [
        "# Phase 9 results",
        "",
        "Numbers below are copied from JSON keys. Virtual-clock task success is not a SLO quote.",
        "Realtime TTFA is the only TTFA that may be quoted; this run did not invent it.",
        "",
        "## Matrix",
        "",
        f"- `n`: {n}",
        f"- `requested_n`: {requested}",
        f"- `elapsed_s`: {elapsed}",
        f"- `time_scale`: {scale}",
        f"- `clock`: {clock}",
        f"- `task_success`: {success}",
        "",
        "## Smoke",
        "",
        f"- `n`: {(smoke or {}).get('n')}",
        f"- `task_success`: {(smoke or {}).get('task_success')}",
        f"- `slot_f1_gate`: {(smoke or {}).get('slot_f1_gate')}",
        "",
        "## Realtime",
        "",
        f"- `status`: {rt_status}",
        f"- `n`: {rt_n}",
        f"- `reason`: {rt_reason}",
        "",
        "## Ablations",
        "",
    ]
    for name, row in ablations.items():
        if isinstance(row, dict):
            lines.append(f"- `{name}`: status=`{row.get('status')}` n=`{row.get('n')}`")
        else:
            lines.append(f"- `{name}`: {row}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=Path("docs/results/phase9_matrix.json"))
    parser.add_argument("--realtime", type=Path, default=Path("docs/results/phase9_realtime.json"))
    parser.add_argument(
        "--ablations", type=Path, default=Path("docs/results/phase9_ablations.json")
    )
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase9.md"))
    parser.add_argument("--smoke", type=Path, default=Path("docs/results/smoke_artifact.json"))
    args = parser.parse_args(argv)
    matrix = json.loads(args.matrix.read_text(encoding="utf-8")) if args.matrix.is_file() else {}
    realtime = (
        json.loads(args.realtime.read_text(encoding="utf-8")) if args.realtime.is_file() else {}
    )
    ablations = (
        json.loads(args.ablations.read_text(encoding="utf-8")) if args.ablations.is_file() else {}
    )
    smoke = json.loads(args.smoke.read_text(encoding="utf-8")) if args.smoke.is_file() else {}
    args.out.write_text(render(matrix, realtime, ablations, smoke), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
