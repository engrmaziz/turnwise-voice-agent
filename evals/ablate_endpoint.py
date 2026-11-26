"""Silence-only versus hybrid endpointing. Result or blocked."""

from __future__ import annotations

from pathlib import Path

from server.config import Settings


def run(*, settings: Settings, out: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "endpoint_silence_vs_hybrid",
        "status": "blocked",
        "reason": "matrix_n_not_900",
        "n": 0,
        "method": "turn_model_enabled false versus true",
        "columns": ["early_cutoff", "response_gap"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json(payload), encoding="utf-8")
    return payload


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
