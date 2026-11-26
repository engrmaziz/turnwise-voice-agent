"""Zipformer versus Whisper+LA-2 on the same fixtures. Missing weights stay blocked."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bench.schema import BenchRow
from server.config import Settings

FIXTURES = (
    "book tuesday at two thirty",
    "cancel my appointment with doctor lang",
    "reschedule to next wednesday",
    "I need a checkup tomorrow",
    "is doctor okonkwo available friday",
    "the day after tomorrow at three o'clock",
    "speak to a human please",
    "what are your hours",
    "chest pain and cannot breathe",
    "appointment for march third",
    "phone number five five five one two one two",
    "see doctor qadir this thursday",
    "book with doctor voss next monday",
    "cancel friday morning",
    "follow up with doctor chaudhry",
    "is the clinic open today",
    "need blood work next tuesday",
    "doctor hale after lunch",
    "move it to this saturday",
    "new patient with doctor sorenson",
)


def measure_asr_compare(settings: Settings) -> list[BenchRow]:
    """Twenty text fixtures. Audio decode stays blocked until weights exist."""
    del settings
    if len(FIXTURES) != 20:
        raise RuntimeError("phase 3 compare set must be 20 fixtures")
    reason = "weights_unpinned"
    rows: list[BenchRow] = []
    for backend in ("zipformer", "whisper_la2"):
        extra: dict[str, object] = {
            "fixtures": len(FIXTURES),
            "stabilization_delay_ms_p50": None,
            "stabilization_delay_ms_p95": None,
            "delay_basis": "utterance_end",
        }
        rows.append(
            BenchRow(
                name=f"asr.compare.{backend}.finalize",
                status="blocked",
                reason=reason,
                extra=extra,
            )
        )
        rows.append(
            BenchRow(
                name=f"asr.compare.{backend}.stabilization",
                status="blocked",
                reason=reason,
                extra=extra,
            )
        )
    return rows


def write_compare_json(rows: list[BenchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.model_dump() for row in rows]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
