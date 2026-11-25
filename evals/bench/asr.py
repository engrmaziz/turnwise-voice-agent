"""ASR finalize and real-time factor. Missing weights become ``blocked`` rows."""

from __future__ import annotations

import importlib
from pathlib import Path

from evals.bench.agreement import local_agreement_2
from evals.bench.harness import blocked_row
from evals.bench.schema import BenchRow
from server.config import Settings

# Aesop, public domain. The WAV is generated only when a speech synthesizer exists.
FIXTURE_TEXT = "The north wind and the sun were disputing which was the stronger."
FIXTURE_LICENSE = "public-domain"


def measure_asr(settings: Settings, *, speech_wav: Path | None) -> list[BenchRow]:
    """Zipformer and Whisper+LA-2. No millisecond is invented when a probe fails."""
    if speech_wav is None or not speech_wav.is_file():
        reason = "no_speech_fixture"
        return [
            blocked_row("asr.zipformer.finalize", reason),
            blocked_row("asr.whisper_la2.finalize", reason),
            blocked_row("asr.whisper_la2.stabilization", reason),
        ]
    return [
        _zipformer(settings),
        *_whisper(settings),
    ]


def _module_version(module_name: str) -> tuple[object | None, str | None, str | None]:
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None, None, f"import_{module_name}"
    version = getattr(module, "__version__", None)
    printed = str(version) if version is not None else f"{module_name}-unknown"
    return module, printed, None


def _zipformer(settings: Settings) -> BenchRow:
    _module, version, import_reason = _module_version("sherpa_onnx")
    if import_reason is not None:
        return blocked_row("asr.zipformer.finalize", import_reason)
    model_dir = settings.bench_sherpa_model_dir.strip()
    if not model_dir or not Path(model_dir).is_dir():
        return blocked_row("asr.zipformer.finalize", "missing_model_dir", version=version)
    # Running decode without a pinned model layout would invent a protocol.
    # The row stays blocked until T3.1.1 names the exact encoder/decoder files.
    return blocked_row(
        "asr.zipformer.finalize",
        "model_layout_unpinned",
        version=version,
    )


def _whisper(settings: Settings) -> list[BenchRow]:
    _module, version, import_reason = _module_version("faster_whisper")
    finalize = "asr.whisper_la2.finalize"
    stabilize = "asr.whisper_la2.stabilization"
    if import_reason is not None:
        return [
            blocked_row(finalize, import_reason),
            blocked_row(stabilize, import_reason),
        ]
    model = settings.bench_whisper_model.strip()
    if not model:
        return [
            blocked_row(finalize, "missing_model", version=version),
            blocked_row(stabilize, "missing_model", version=version),
        ]
    return [
        blocked_row(finalize, "model_layout_unpinned", version=version),
        blocked_row(stabilize, "model_layout_unpinned", version=version),
    ]


def agreement_prefix(first: str, second: str) -> str:
    """Exported for tests. Used by the Whisper row once a decoder exists."""
    return local_agreement_2(first, second)
