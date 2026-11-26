"""Grammar-constrained teacher. Invalid JSON or unknown slot keys drop the row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from nlp.nlu_vocab import INTENTS, SLOT_KEYS
from training.nlu.schema import AsrTrainRow


class TeacherLabel(BaseModel):
    intent: str
    slots: dict[str, str]

    @field_validator("intent")
    @classmethod
    def known_intent(cls, value: str) -> str:
        if value not in INTENTS:
            raise ValueError("unknown intent")
        return value

    @field_validator("slots")
    @classmethod
    def known_slots(cls, value: dict[str, str]) -> dict[str, str]:
        for key in value:
            if key not in SLOT_KEYS:
                raise ValueError(f"slot key outside schema: {key}")
        return value


def parse_teacher_json(raw: str) -> TeacherLabel | None:
    """Return a label or None. Grammar reject is a drop, not a regex patch."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return TeacherLabel.model_validate(payload)
    except ValidationError:
        return None


def apply_teacher_file(rows_path: Path, labels_path: Path, out_path: Path) -> int:
    """Keep rows whose teacher JSON validates. Returns dropped count."""
    labels = {
        item["script_id"]: item["teacher_json"]
        for item in _read_jsonl(labels_path)
        if "script_id" in item and "teacher_json" in item
    }
    kept = 0
    dropped = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for raw in rows_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            row = AsrTrainRow.model_validate_json(raw)
            blob = labels.get(row.script_id)
            if blob is None:
                dropped += 1
                continue
            parsed = parse_teacher_json(str(blob))
            if parsed is None:
                dropped += 1
                continue
            if parsed.intent != row.intent and row.asr_text.strip():
                dropped += 1
                continue
            handle.write(row.model_dump_json() + "\n")
            kept += 1
    print(f"rows_kept={kept} rows_dropped={dropped}")
    return dropped


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=Path("training/nlu/asr_rows.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("training/nlu/teacher_labels.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("training/nlu/teacher_kept.jsonl"))
    args = parser.parse_args(argv)
    if not args.labels.is_file():
        print("rows_dropped=all teacher=blocked_llm")
        return 0
    apply_teacher_file(args.rows, args.labels, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
