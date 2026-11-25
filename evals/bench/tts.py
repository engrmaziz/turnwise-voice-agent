"""TTS first-chunk. CPU is mandatory. GPU is ``not_present`` when nvidia-smi fails."""

from __future__ import annotations

import shutil
from pathlib import Path

from evals.bench.harness import blocked_row, not_present_row
from evals.bench.host import probe_nvidia
from evals.bench.schema import BenchRow
from server.config import Settings


def measure_tts(settings: Settings, *, nvidia_smi: str | None = None) -> list[BenchRow]:
    cpu = _cpu_row(settings)
    gpu_status, _detail = probe_nvidia(nvidia_smi)
    if gpu_status == "not_present":
        gpu = not_present_row("tts.first_chunk.gpu", "nvidia_smi_failed")
    else:
        gpu = blocked_row("tts.first_chunk.gpu", "model_layout_unpinned")
    return [cpu, gpu]


def _cpu_row(settings: Settings) -> BenchRow:
    binary = _tts_binary(settings)
    if binary is None:
        piper = _module_missing("piper")
        kokoro = _module_missing("kokoro")
        return blocked_row("tts.first_chunk.cpu", f"missing_tts:{piper},{kokoro}")
    return blocked_row("tts.first_chunk.cpu", "model_layout_unpinned", version=binary)


def _tts_binary(settings: Settings) -> str | None:
    configured = settings.bench_tts_command.strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return configured
        return shutil.which(configured)
    for name in ("piper", "kokoro"):
        found = shutil.which(name)
        if found is not None:
            return found
    return None


def _module_missing(name: str) -> str:
    try:
        __import__(name)
    except ImportError:
        return f"import_{name}"
    return f"{name}_no_weights"
