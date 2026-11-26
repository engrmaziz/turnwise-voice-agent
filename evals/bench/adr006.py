"""ADR-006 is rendered from compare JSON so a missing p50 cannot become a pick."""

from __future__ import annotations

from evals.bench.schema import BenchRow

_TARGET_MS = 100.0


def choose_backend(rows: list[BenchRow]) -> tuple[str, str]:
    """Return (backend_or_blocked, reason). Never averages two backends."""
    zip_row = _named(rows, "asr.compare.zipformer.finalize")
    whisper_row = _named(rows, "asr.compare.whisper_la2.finalize")
    if zip_row is None or whisper_row is None:
        return "blocked", "Compare JSON is missing a finalize row."
    zip_ok = zip_row.status == "ok" and zip_row.p50_ms is not None
    whisper_ok = whisper_row.status == "ok" and whisper_row.p50_ms is not None
    if not zip_ok and not whisper_ok:
        return "blocked", "Both ASR backends are blocked; asr_backend stays empty."
    if zip_ok and not whisper_ok:
        return _pick("zipformer", zip_row.p50_ms)
    if whisper_ok and not zip_ok:
        return _pick("whisper_la2", whisper_row.p50_ms)
    assert zip_row.p50_ms is not None and whisper_row.p50_ms is not None
    if zip_row.p50_ms <= whisper_row.p50_ms:
        return _pick("zipformer", zip_row.p50_ms)
    return _pick("whisper_la2", whisper_row.p50_ms)


def render_adr006(rows: list[BenchRow], *, json_path: str) -> str:
    choice, reason = choose_backend(rows)
    missed = ""
    if choice not in {"blocked", ""}:
        row = _named(rows, f"asr.compare.{choice}.finalize")
        if row is not None and row.p50_ms is not None and row.p50_ms > _TARGET_MS:
            missed = f" Finalize p50 {row.p50_ms:.1f} ms misses the {_TARGET_MS:.0f} ms TARGET."
    lines = [
        "# ADR-006: ASR backend",
        "",
        "- Status: Proposed" if choice == "blocked" else "- Status: Accepted",
        "- Date: 2026-11-27",
        "",
        "## Context",
        "",
        "Phase 3 must name Zipformer or Whisper plus LocalAgreement-2 from measured "
        "finalize p50 on this machine. A copied number from a paper is not a measurement.",
        "",
        f"JSON: `{json_path}`",
        "",
        "## Decision",
        "",
    ]
    if choice == "blocked":
        lines.extend(
            [
                f"The ASR backend is **blocked**. {reason} "
                "`TURNWISE_ASR_BACKEND` stays empty so the call path uses the stub. "
                "ADR-003 stays Proposed.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"The ASR backend is **{choice}**. {reason}{missed}",
                "",
            ]
        )
    lines.extend(
        [
            "## Consequences",
            "",
            "- Default `TURNWISE_ASR_BACKEND` stays empty so CI stays weight-free. "
            "Operators set it to the chosen backend after `uv sync --extra asr` "
            "and `python scripts/download_models.py`.",
            "- Hotword entity WER is a separate JSON; an `unsupported` on-row is not a zero.",
            "- ADR-003 stays Proposed until LLM rows are also chosen.",
            "",
        ]
    )
    return "\n".join(lines)


def _pick(name: str, p50_ms: float | None) -> tuple[str, str]:
    if p50_ms is None:
        return "blocked", f"{name} has no p50."
    return name, f"{name} finalize p50 is {p50_ms:.1f} ms."


def _named(rows: list[BenchRow], name: str) -> BenchRow | None:
    for row in rows:
        if row.name == name:
            return row
    return None
