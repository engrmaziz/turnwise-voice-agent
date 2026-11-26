"""Clean-text student versus ASR-trained student. Blocked until T5.4.1 --clean exists."""

from __future__ import annotations

from pathlib import Path

from server.config import Settings


def run(*, settings: Settings, out: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "nlu_clean_vs_asr",
        "status": "blocked",
        "reason": "clean_text_student_never_trained",
        "n": 0,
        "method": "two student checkpoints; T5.4.1 --clean is slip",
        "columns": ["slot_f1", "task_success"],
        "nlu_model_path": settings.nlu_model_path,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json(payload), encoding="utf-8")
    return payload


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
