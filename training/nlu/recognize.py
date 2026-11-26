"""Recognize rendered scripts. Real backends are blocked; CI uses a stub substitution."""

from __future__ import annotations

import argparse
from pathlib import Path

from nlp.nlu_features import tokenize
from training.nlu.align_bio import bio_from_slots, project_bio
from training.nlu.generate import load_jsonl
from training.nlu.schema import AsrTrainRow

FORCED_SUB = ("Lang", "Lan")


def stub_asr(clean: str) -> str:
    """Return the clean text with one forced substitution so CI can align."""
    needle, repl = FORCED_SUB
    if needle in clean:
        return clean.replace(needle, repl, 1)
    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0]} uh {' '.join(parts[1:])}"
    return f"{clean} uh"


def recognize_scripts(scripts_path: Path, out_path: Path) -> list[AsrTrainRow]:
    rows: list[AsrTrainRow] = []
    for script in load_jsonl(scripts_path):
        asr_text = stub_asr(script.text)
        clean_tokens = tokenize(script.text)
        clean_tags = bio_from_slots(script.text, script.slots)
        asr_tokens = tokenize(asr_text)
        bio, align_low = project_bio(clean_tokens, clean_tags, asr_tokens)
        rows.append(
            AsrTrainRow(
                script_id=script.script_id,
                spoken_clean=script.text,
                asr_text=asr_text,
                intent=script.intent,
                bio_asr=bio,
                align_low=align_low,
            )
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scripts", type=Path, default=Path("training/nlu/fixture_scripts.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    args = parser.parse_args(argv)
    rows = recognize_scripts(args.scripts, args.out)
    print(f"asr_backend=stub rows={len(rows)} forced_sub={FORCED_SUB[0]}->{FORCED_SUB[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
