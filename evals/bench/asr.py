"""ASR finalize and real-time factor. Missing weights become ``blocked`` rows."""

from __future__ import annotations

import importlib
import importlib.util
import time
import wave
from pathlib import Path

import numpy as np

from evals.bench.agreement import local_agreement_2
from evals.bench.harness import blocked_row, ok_row, percentile
from evals.bench.schema import BenchRow
from models.asr_zipformer import load_zipformer_recognizer, pcm16_to_float32, warmup_recognizer
from pipeline.audio.format import resample_mono_pcm16
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
        _zipformer(settings, speech_wav),
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


def _zipformer(settings: Settings, speech_wav: Path) -> BenchRow:
    if importlib.util.find_spec("sherpa_onnx") is None:
        return blocked_row("asr.zipformer.finalize", "import_sherpa_onnx")
    encoder = Path(settings.asr_zipformer_encoder_path)
    decoder = Path(settings.asr_zipformer_decoder_path)
    joiner = Path(settings.asr_zipformer_joiner_path)
    tokens = Path(settings.asr_zipformer_tokens_path)
    if not all(path.is_file() for path in (encoder, decoder, joiner, tokens)):
        return blocked_row("asr.zipformer.finalize", "missing_model_dir")
    try:
        recognizer = load_zipformer_recognizer(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            sample_rate=settings.ws_sample_rate_hz,
            hotword_score=settings.hotword_score,
        )
        warmup_recognizer(recognizer, settings.ws_sample_rate_hz)
        samples, rate = _wav_float32(speech_wav, settings.ws_sample_rate_hz)
        p50, p95, text = _time_finalize(
            recognizer,
            samples,
            rate,
            warmup=settings.bench_warmup,
            count=settings.bench_samples,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return blocked_row(
            "asr.zipformer.finalize",
            f"zipformer_failed:{type(exc).__name__}",
        )
    printed = _module_version("sherpa_onnx")[1]
    version = printed or "sherpa-onnx-unknown"
    return ok_row(
        "asr.zipformer.finalize",
        version=f"{version};zipformer2;int8;en-2023-06-26",
        p50_ms=p50,
        p95_ms=p95,
        extra={"text": text, "wav": speech_wav.as_posix()},
    )


def _time_finalize(
    recognizer: object,
    samples: np.ndarray,
    rate: int,
    *,
    warmup: int,
    count: int,
) -> tuple[float, float, str]:
    tail = np.zeros(int(0.5 * rate), dtype=np.float32)
    elapsed: list[float] = []
    text = ""
    total = warmup + count
    for index in range(total):
        stream = recognizer.create_stream()  # type: ignore[attr-defined]
        stream.accept_waveform(rate, samples)
        while recognizer.is_ready(stream):  # type: ignore[attr-defined]
            recognizer.decode_stream(stream)  # type: ignore[attr-defined]
        started = time.perf_counter()
        stream.accept_waveform(rate, tail)
        stream.input_finished()
        while recognizer.is_ready(stream):  # type: ignore[attr-defined]
            recognizer.decode_stream(stream)  # type: ignore[attr-defined]
        text = str(recognizer.get_result(stream))  # type: ignore[attr-defined]
        if index >= warmup:
            elapsed.append((time.perf_counter() - started) * 1000.0)
    return percentile(elapsed, 50.0), percentile(elapsed, 95.0), text


def _wav_float32(path: Path, dst_hz: int) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
            raise ValueError("fixture must be mono PCM16")
        raw = wav.readframes(wav.getnframes())
        src_hz = wav.getframerate()
    pcm = resample_mono_pcm16(raw, src_hz, dst_hz)
    return pcm16_to_float32(pcm), dst_hz


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
