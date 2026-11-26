"""TTS first-chunk. CPU is mandatory. GPU is ``not_present`` when nvidia-smi fails."""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path

from evals.bench.harness import blocked_row, not_present_row, ok_row, time_callable
from evals.bench.host import probe_nvidia
from evals.bench.schema import BenchRow
from models.tts_pool import TtsError, TtsPool
from server.config import Settings

FIRST_CHUNK_TEXT = "Hello this is Turnwise."


def measure_tts(settings: Settings, *, nvidia_smi: str | None = None) -> list[BenchRow]:
    cpu = _cpu_row(settings)
    gpu_status, _detail = probe_nvidia(nvidia_smi)
    if gpu_status == "not_present":
        gpu = not_present_row("tts.first_chunk.gpu", "nvidia_smi_failed")
    else:
        gpu = blocked_row("tts.first_chunk.gpu", "model_layout_unpinned")
    return [cpu, gpu]


def _cpu_row(settings: Settings) -> BenchRow:
    if importlib.util.find_spec("piper") is None:
        return blocked_row(
            "tts.first_chunk.cpu",
            f"missing_tts:import_piper,{_module_status('kokoro')}",
        )
    onnx = Path(settings.tts_piper_onnx_path)
    if not onnx.is_file():
        return blocked_row(
            "tts.first_chunk.cpu",
            f"missing_tts:piper_no_weights,{_module_status('kokoro')}",
        )
    config_raw = settings.tts_piper_config_path.strip()
    config_path = Path(config_raw) if config_raw else None
    timeout_ms = max(1, int(settings.bench_timeout_s * 1000))
    try:
        pool = TtsPool.piper(
            onnx_path=onnx,
            config_path=config_path,
            timeout_ms=timeout_ms,
            output_hz=settings.ws_sample_rate_hz,
        )
    except ImportError:
        return blocked_row(
            "tts.first_chunk.cpu",
            f"missing_tts:import_piper,{_module_status('kokoro')}",
        )
    except (OSError, ValueError, RuntimeError, TtsError) as exc:
        return blocked_row(
            "tts.first_chunk.cpu",
            f"piper_load_failed:{type(exc).__name__}",
            version=_piper_version(),
        )
    text = FIRST_CHUNK_TEXT
    synth = pool.synth_sync
    if synth is None:
        pool.close()
        return blocked_row("tts.first_chunk.cpu", "piper_load_failed:unavailable")

    def run() -> None:
        pcm = synth(text, settings.tts_voice, settings.tts_speed)
        if not pcm:
            raise TtsError("empty pcm")

    try:
        p50, p95, _samples = time_callable(
            run,
            warmup=settings.bench_warmup,
            samples=settings.bench_samples,
        )
    except (OSError, ValueError, RuntimeError, TtsError) as exc:
        pool.close()
        return blocked_row(
            "tts.first_chunk.cpu",
            f"piper_synth_failed:{type(exc).__name__}",
            version=_piper_version(),
        )
    pool.close()
    return ok_row(
        "tts.first_chunk.cpu",
        version=f"{_piper_version()};voice={onnx.stem};device=cpu",
        p50_ms=p50,
        p95_ms=p95,
        extra={
            "text": text,
            "output_hz": settings.ws_sample_rate_hz,
            "onnx": onnx.as_posix(),
        },
    )


def _piper_version() -> str:
    try:
        return f"piper-tts:{importlib.metadata.version('piper-tts')}"
    except importlib.metadata.PackageNotFoundError:
        return "piper-tts:unknown"


def _module_status(name: str) -> str:
    try:
        __import__(name)
    except ImportError:
        return f"import_{name}"
    return f"{name}_no_weights"
