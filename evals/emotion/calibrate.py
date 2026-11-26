"""Reliability table for distressed probability. Refuses missing call-like labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class CalibrationMissingError(ValueError):
    """Call-like labels were not collected; bins must not be invented."""


def load_call_like(path: Path) -> list[dict[str, object]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise CalibrationMissingError("call-like file is empty")
    first = json.loads(raw.splitlines()[0])
    if not isinstance(first, dict):
        raise CalibrationMissingError("call-like row is not an object")
    if str(first.get("status", "")).strip() == "not_collected":
        raise CalibrationMissingError("not_collected")
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CalibrationMissingError("call-like row is not an object")
        if "label" not in payload:
            raise CalibrationMissingError("call-like row missing label")
        rows.append(payload)
    if len(rows) < 30:
        raise CalibrationMissingError("need 30 labeled utterances")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--call-like",
        type=Path,
        default=Path("training/emotion/call_like.jsonl"),
    )
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase8_calibration.csv"))
    args = parser.parse_args(argv)
    try:
        load_call_like(args.call_like)
    except CalibrationMissingError as exc:
        sys.stderr.write(f"calibrate refused: {exc}\n")
        return 2
    sys.stderr.write("calibrate refused: ECE writer is not implemented without a model\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
