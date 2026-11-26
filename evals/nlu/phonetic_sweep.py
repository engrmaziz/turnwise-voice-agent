"""Sweep phonetic_min_score and phonetic_margin. Writes untuned when golden is incomplete."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp.phonetic import resolve_entity
from server.config import Settings
from training.nlu.schema import GoldenRow


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
            "kept": {"phonetic_min_score": 0.82, "phonetic_margin": 0.05},
        }
    grid = []
    settings = Settings()
    for min_score in (0.75, 0.82, 0.9):
        for margin in (0.03, 0.05, 0.08):
            tuned = settings.model_copy(
                update={"phonetic_min_score": min_score, "phonetic_margin": margin}
            )
            resolved = 0
            for row in rows:
                if "doctor" not in " ".join(row.bio_asr):
                    continue
                heard = " ".join(
                    tok
                    for tok, tag in zip(row.asr_text.split(), row.bio_asr, strict=False)
                    if tag.endswith("doctor")
                )
                if not heard:
                    continue
                result = resolve_entity(heard, ["Dr. Avery Lang", "Dr. Nia Okonkwo"], tuned)
                if result.entity_id is not None:
                    resolved += 1
            grid.append({"min": min_score, "margin": margin, "resolved": resolved})
    return {"status": "swept", "grid": grid}


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
            "Production keeps `phonetic_min_score=0.82` and `phonetic_margin=0.05`.\n"
        )
    else:
        lines = ["# Phase 5 phonetic sweep", "", "| min | margin | resolved |", "|---|---|---|"]
        grid = result.get("grid")
        if not isinstance(grid, list):
            raise TypeError("swept result missing grid")
        for item in grid:
            if not isinstance(item, dict):
                continue
            lines.append(f"| {item['min']} | {item['margin']} | {item['resolved']} |")
        body = "\n".join(lines) + "\n"
    args.out.write_text(body, encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
