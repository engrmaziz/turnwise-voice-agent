"""Sweep phonetic_min_score and phonetic_margin. Writes untuned when golden is incomplete."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp.hotwords import load_roster
from nlp.nlu_features import tokenize
from nlp.phonetic import resolve_entity
from server.config import Settings
from training.nlu.schema import GoldenRow

STARTING_MIN = 0.82
STARTING_MARGIN = 0.05


def sweep_or_untuned(golden_path: Path, *, complete_n: int = 500) -> dict[str, object]:
    if not golden_path.is_file():
        return {"status": "untuned", "reason": "golden_missing"}
    rows: list[GoldenRow] = []
    for raw in golden_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict) or "reviewer" not in payload:
            return {"status": "untuned", "reason": "golden_incomplete"}
        rows.append(GoldenRow.model_validate(payload))
    if len(rows) < complete_n:
        return {
            "status": "untuned",
            "reason": "golden_incomplete",
            "n": len(rows),
            "kept": {"phonetic_min_score": STARTING_MIN, "phonetic_margin": STARTING_MARGIN},
        }
    catalog = list(load_roster(Path(Settings().doctor_roster_path)))
    grid: list[dict[str, float | int]] = []
    settings = Settings()
    for min_score in (0.75, 0.82, 0.9):
        for margin in (0.03, 0.05, 0.08):
            tuned = settings.model_copy(
                update={"phonetic_min_score": min_score, "phonetic_margin": margin}
            )
            resolved = 0
            correct = 0
            eligible = 0
            for row in rows:
                heard = _heard_doctor(row)
                gold = _gold_doctor(row.spoken_clean, catalog)
                if not heard or gold is None:
                    continue
                eligible += 1
                result = resolve_entity(heard, catalog, tuned)
                if result.entity_id is not None:
                    resolved += 1
                    if result.entity_id == gold:
                        correct += 1
            grid.append(
                {
                    "min": min_score,
                    "margin": margin,
                    "resolved": resolved,
                    "correct": correct,
                    "eligible": eligible,
                }
            )
    winner = _pick_cell(grid)
    return {"status": "swept", "n": len(rows), "grid": grid, "winner": winner}


def _gold_doctor(spoken_clean: str, catalog: list[str]) -> str | None:
    lowered = spoken_clean.lower()
    hits = [name for name in catalog if name.lower() in lowered or _surname(name) in lowered]
    if len(hits) == 1:
        return hits[0]
    return None


def _surname(name: str) -> str:
    return name.replace("Dr.", " ").strip().split()[-1].lower()


def _heard_doctor(row: GoldenRow) -> str:
    tokens = tokenize(row.asr_text)
    if len(tokens) != len(row.bio_asr):
        return ""
    heard = [
        token
        for token, tag in zip(tokens, row.bio_asr, strict=True)
        if tag.endswith("doctor")
    ]
    return " ".join(heard)


def _pick_cell(grid: list[dict[str, float | int]]) -> dict[str, float | int]:
    if not grid:
        return {"min": STARTING_MIN, "margin": STARTING_MARGIN, "resolved": 0}
    best = max(grid, key=lambda cell: (int(cell.get("correct", 0)), int(cell["resolved"])))
    tied = [
        cell
        for cell in grid
        if cell.get("correct") == best.get("correct") and cell["resolved"] == best["resolved"]
    ]
    for cell in tied:
        if cell["min"] == STARTING_MIN and cell["margin"] == STARTING_MARGIN:
            return cell
    return tied[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=Path("training/nlu/golden.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("docs/results/phase5_phonetic.md"))
    args = parser.parse_args(argv)
    result = sweep_or_untuned(args.golden)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if result["status"] == "untuned":
        extra = f" n={result['n']}." if "n" in result else ""
        body = (
            "# Phase 5 phonetic sweep\n\n"
            f"Status: **untuned**. Reason: `{result.get('reason')}`.{extra} "
            f"Production keeps `phonetic_min_score={STARTING_MIN}` and "
            f"`phonetic_margin={STARTING_MARGIN}`.\n"
        )
    else:
        lines = [
            "# Phase 5 phonetic sweep",
            "",
            f"n={result.get('n')} Zipformer-ASR golden rows. Catalog: `data/doctors.txt`.",
            "",
            "| min | margin | correct | resolved | eligible |",
            "|---|---|---|---|---|",
        ]
        grid = result.get("grid")
        if not isinstance(grid, list):
            raise TypeError("swept result missing grid")
        for item in grid:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item['min']} | {item['margin']} | {item.get('correct', '')} | "
                f"{item['resolved']} | {item.get('eligible', '')} |"
            )
        winner = result.get("winner")
        if isinstance(winner, dict):
            lines.extend(
                [
                    "",
                    f"Winner: min=`{winner['min']}` margin=`{winner['margin']}` "
                    f"correct={winner.get('correct')} resolved={winner['resolved']}. "
                    "Starting point 0.82/0.05 is kept when tied. Production updates only when "
                    "this cell beats the starting point on **correct** ids.",
                ]
            )
        body = "\n".join(lines) + "\n"
    args.out.write_text(body, encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
