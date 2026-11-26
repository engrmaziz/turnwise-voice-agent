"""Sample golden rows. Oversample align_low and guarantee every intent appears."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from nlp.nlu_vocab import INTENTS
from training.nlu.schema import AsrTrainRow, GoldenRow


def sample_golden(
    rows: list[AsrTrainRow],
    *,
    size: int,
    reviewer: str,
    reviewed_at: str,
) -> list[GoldenRow]:
    if size < 1:
        raise ValueError("size must be >= 1")
    by_intent: dict[str, list[AsrTrainRow]] = defaultdict(list)
    low: list[AsrTrainRow] = []
    for row in rows:
        by_intent[row.intent].append(row)
        if row.align_low:
            low.append(row)
    picked: list[AsrTrainRow] = []
    seen: set[str] = set()
    for intent in INTENTS:
        bucket = by_intent.get(intent, [])
        if not bucket:
            continue
        item = bucket[0]
        picked.append(item)
        seen.add(item.script_id)
    for item in low:
        if item.script_id in seen:
            continue
        picked.append(item)
        seen.add(item.script_id)
        if len(picked) >= size:
            break
    for row in rows:
        if row.script_id in seen:
            continue
        picked.append(row)
        seen.add(row.script_id)
        if len(picked) >= size:
            break
    stamp = reviewed_at
    return [
        GoldenRow(
            **item.model_dump(),
            reviewer=reviewer,
            reviewed_at=stamp,
            changed=False,
        )
        for item in picked[:size]
    ]


def intent_report(rows: list[GoldenRow]) -> dict[str, int]:
    counts = dict.fromkeys(INTENTS, 0)
    for row in rows:
        counts[row.intent] = counts.get(row.intent, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("training/nlu/golden_fixture.jsonl"))
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--reviewer", default="engrmaziz")
    args = parser.parse_args(argv)
    raw_rows = [
        AsrTrainRow.model_validate_json(line)
        for line in args.rows.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    golden = sample_golden(raw_rows, size=args.size, reviewer=args.reviewer, reviewed_at=stamp)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in golden:
            handle.write(row.model_dump_json() + "\n")
    report = {"intents": intent_report(golden), "n": len(golden)}
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
