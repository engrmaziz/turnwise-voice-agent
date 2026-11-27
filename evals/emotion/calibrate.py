"""Reliability table for distressed probability. Refuses missing call-like labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
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


def scored_pairs(rows: list[dict[str, object]]) -> list[tuple[float, int]]:
    """Each row needs a model score in [0, 1] and a binary distressed label."""
    pairs: list[tuple[float, int]] = []
    for row in rows:
        score = _score(row)
        label = _distressed(row["label"])
        if score is None:
            continue
        pairs.append((score, label))
    if len(pairs) < 30:
        raise CalibrationMissingError("need 30 scored labeled utterances")
    return pairs


def expected_calibration_error(
    pairs: list[tuple[float, int]],
    *,
    bins: int = 10,
) -> tuple[float, list[dict[str, object]]]:
    if bins < 1:
        raise ValueError("bins must be >= 1")
    if not pairs:
        raise CalibrationMissingError("no scored rows")
    width = 1.0 / bins
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for score, label in pairs:
        clipped = min(1.0, max(0.0, score))
        index = min(bins - 1, int(clipped / width) if clipped < 1.0 else bins - 1)
        buckets[index].append((clipped, label))
    table: list[dict[str, object]] = []
    ece = 0.0
    total = len(pairs)
    for index, bucket in enumerate(buckets):
        lo = index * width
        hi = (index + 1) * width
        count = len(bucket)
        if count == 0:
            table.append(
                {
                    "bin": index,
                    "low": lo,
                    "high": hi,
                    "n": 0,
                    "confidence": "",
                    "accuracy": "",
                    "abs_gap": "",
                }
            )
            continue
        confidence = sum(score for score, _label in bucket) / count
        accuracy = sum(label for _score, label in bucket) / count
        gap = abs(accuracy - confidence)
        ece += (count / total) * gap
        table.append(
            {
                "bin": index,
                "low": lo,
                "high": hi,
                "n": count,
                "confidence": confidence,
                "accuracy": accuracy,
                "abs_gap": gap,
            }
        )
    if not math.isfinite(ece):
        raise CalibrationMissingError("ece is not finite")
    return ece, table


def write_reliability_csv(
    path: Path,
    *,
    ece: float,
    table: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("bin", "low", "high", "n", "confidence", "accuracy", "abs_gap", "ece"),
        )
        writer.writeheader()
        for index, row in enumerate(table):
            payload = dict(row)
            payload["ece"] = ece if index == 0 else ""
            writer.writerow(payload)


def _score(row: dict[str, object]) -> float | None:
    for key in ("score", "p_distressed", "distressed"):
        raw = row.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            continue
        return float(raw)
    return None


def _distressed(label: object) -> int:
    text = str(label).strip().casefold()
    if text in {"1", "true", "distressed", "frustrated"}:
        return 1
    if text in {"0", "false", "calm"}:
        return 0
    raise CalibrationMissingError(f"unrecognized label {label!r}")


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
        rows = load_call_like(args.call_like)
        pairs = scored_pairs(rows)
        ece, table = expected_calibration_error(pairs)
    except CalibrationMissingError as exc:
        sys.stderr.write(f"calibrate refused: {exc}\n")
        return 2
    write_reliability_csv(args.out, ece=ece, table=table)
    sys.stdout.write(f"ece={ece}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
