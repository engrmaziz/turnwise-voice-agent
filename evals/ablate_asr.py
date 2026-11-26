"""Zipformer versus Whisper+LocalAgreement-2. Blocked if a backend never imported."""

from __future__ import annotations

from pathlib import Path

from server.config import Settings


def run(*, settings: Settings, out: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "zipformer_vs_whisper_la2",
        "status": "blocked",
        "reason": "missing_asr:import_sherpa,import_whisper",
        "n": 0,
        "method": "TTFA and entity WER; ADR-006 comparison",
        "asr_backend": settings.asr_backend,
        "columns": ["ttfa", "entity_wer"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json(payload), encoding="utf-8")
    return payload


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
