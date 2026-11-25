"""ADR-004 is rendered from the JSON log so a hand edit cannot invent a tier."""

from __future__ import annotations

from evals.bench.harness import measured_ok
from evals.bench.schema import BenchReport

_TIERS = ("CPU-only", "8 GB", "16 GB+")


def decide_tier(report: BenchReport) -> tuple[str, str]:
    """Return (tier_or_blocked, reason). Never names a tier from missing rows."""
    asr_ok = measured_ok(report, "asr.")
    llm_ok = measured_ok(report, "llm.")
    tts_ok = measured_ok(report, "tts.first_chunk.cpu")
    if not (asr_ok and llm_ok and tts_ok):
        missing = []
        if not asr_ok:
            missing.append("ASR finalize")
        if not llm_ok:
            missing.append("LLM TTFT")
        if not tts_ok:
            missing.append("TTS first-chunk CPU")
        return "blocked", "Missing measured rows: " + ", ".join(missing) + "."
    if report.host.nvidia_status == "not_present":
        return "CPU-only", "nvidia-smi not_present; CPU-only is the only eligible tier."
    vram = _vram_gb(report.host.nvidia_smi)
    if vram is None:
        return "blocked", "GPU present but VRAM could not be parsed from nvidia-smi."
    if vram >= 16:
        return "16 GB+", f"nvidia-smi VRAM {vram:.0f} GB"
    if vram >= 8:
        return "8 GB", f"nvidia-smi VRAM {vram:.0f} GB"
    return "CPU-only", f"nvidia-smi VRAM {vram:.0f} GB is below the 8 GB tier."


def render_adr(report: BenchReport) -> str:
    tier, reason = decide_tier(report)
    status = "Proposed"
    lines = [
        "# ADR-004: Hardware tier",
        "",
        f"- Status: {status}",
        f"- Date: {_date(report.started_utc)}",
        "",
        "## Context",
        "",
        "ADR-003 keeps the model stack Proposed until a bench on this machine "
        "records ASR finalize, language-model time-to-first-token, and TTS "
        "first-chunk. The tiers in `docs/plan/00_front_matter.md` are CPU-only, "
        "8 GB VRAM, and 16 GB+ VRAM. Naming one of those from a missing row "
        "would freeze a guess.",
        "",
        f"Host: `{report.host.platform}`",
        f"Python: `{report.host.python}`",
        f"JSON: `{report.json_path}`",
        "",
        "## Decision",
        "",
    ]
    if tier == "blocked":
        lines.extend(
            [
                f"The hardware tier is **blocked**. {reason} "
                "ADR-003 stays Proposed. The next bench that fills those rows "
                "rewrites this ADR from the new JSON.",
                "",
            ]
        )
    else:
        if tier not in _TIERS:
            raise RuntimeError(f"unknown tier {tier}")
        lines.extend(
            [
                f"The operator machine is **{tier}**. {reason} "
                "ADR-003 stays Proposed until a follow-up ADR names exact builds.",
                "",
            ]
        )
    lines.extend(
        [
            "## Consequences",
            "",
            "- A second host writes a second JSON file. It does not edit this one.",
            "- Model names in settings stay unset until ADR-003 is Accepted.",
            "- `docs/benchmarks.md` is generated from the same JSON as this ADR.",
            "",
        ]
    )
    return "\n".join(lines)


def _date(started_utc: str) -> str:
    if len(started_utc) >= 8 and started_utc[:8].isdigit():
        return f"{started_utc[0:4]}-{started_utc[4:6]}-{started_utc[6:8]}"
    return started_utc[:10]


def _vram_gb(smi: str | None) -> float | None:
    if not smi:
        return None
    # csv noheader nounits: "NVIDIA GeForce RTX 3070, 8192"
    last = smi.splitlines()[0].split(",")[-1].strip()
    try:
        megabytes = float(last)
    except ValueError:
        return None
    return megabytes / 1024.0
