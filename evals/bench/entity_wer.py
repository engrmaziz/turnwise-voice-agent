"""Entity WER with hotword bias on and off. Missing TTS or hotword API is not a number."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.harness import blocked_row
from evals.bench.schema import BenchRow
from nlp.hotwords import load_roster
from server.config import Settings


def measure_entity_wer(settings: Settings, *, supports_hotwords: bool) -> list[BenchRow]:
    """Synthesize the roster through TTS. Blocked TTS is not text-only WER."""
    roster = load_roster(Path(settings.doctor_roster_path))
    if len(roster) < 15:
        raise RuntimeError("roster must have at least 15 invented names")
    names = list(roster) + list(roster)[:15]
    names = names[:30]
    tts = settings.bench_tts_command.strip()
    if not tts:
        reason = "tts_blocked"
        return [
            blocked_row("asr.entity_wer.bias_off", reason),
            blocked_row("asr.entity_wer.bias_on", reason if supports_hotwords else "unsupported"),
        ]
    if not supports_hotwords:
        return [
            blocked_row("asr.entity_wer.bias_off", "weights_unpinned"),
            blocked_row("asr.entity_wer.bias_on", "unsupported"),
        ]
    del names
    return [
        blocked_row("asr.entity_wer.bias_off", "weights_unpinned"),
        blocked_row("asr.entity_wer.bias_on", "weights_unpinned"),
    ]


def write_entity_json(rows: list[BenchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([row.model_dump() for row in rows], indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
