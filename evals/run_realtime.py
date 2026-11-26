"""Realtime subset. Records skip when the operator did not run wall-clock calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.config import Settings


def run_realtime(*, n: int, out: Path, settings: Settings) -> dict[str, object]:
    """Do not invent TTFA. Virtual-clock numbers must not be labeled realtime."""
    reason = (
        "eval_time_scale is virtual"
        if settings.eval_time_scale != 1.0
        else "realtime_pcm_driver_not_run"
    )
    payload: dict[str, object] = {
        "status": "skipped",
        "reason": reason,
        "n": 0,
        "requested_n": n,
        "clock": "realtime",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase9_realtime.json"))
    args = parser.parse_args(argv)
    settings = Settings()
    run_realtime(n=settings.eval_realtime_n, out=args.out, settings=settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
