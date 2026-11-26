"""Hotword bias on versus off. Unsupported if the backend has no API."""

from __future__ import annotations

from pathlib import Path

from server.config import Settings


def run(*, settings: Settings, out: Path) -> dict[str, object]:
    backend = settings.asr_backend.strip()
    status = "unsupported" if backend in {"", "stub"} else "blocked"
    payload: dict[str, object] = {
        "name": "hotword_bias",
        "status": status,
        "reason": "asr_backend_has_no_bias_api" if status == "unsupported" else "missing_weights",
        "n": 0,
        "method": "biasing on versus off",
        "columns": ["entity_wer", "task_success"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json(payload), encoding="utf-8")
    return payload


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
