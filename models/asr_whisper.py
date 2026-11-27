"""faster-whisper LocalAgreement-2 decoder. Import happens at load, not at import."""

from __future__ import annotations

import shutil
import time
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from nlp.local_agreement import LocalAgreement2
from pipeline.audio.format import resample_mono_pcm16
from server.config import Settings

_HF_REPOS = (
    "models--Systran--faster-whisper-tiny.en",
    "models--Systran--faster-whisper-tiny",
    "models--Systran--faster-whisper-base.en",
    "models--Systran--faster-whisper-small.en",
    "models--Systran--faster-whisper-small",
)

_WHISPER_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")
_TINY_EN_BASE = "https://huggingface.co/Systran/faster-whisper-tiny.en/resolve/main"
class _WhisperSegment(Protocol):
    text: str


class _FasterWhisper(Protocol):
    def transcribe(
        self,
        audio: NDArray[np.float32],
        language: str = "en",
        beam_size: int = 1,
        vad_filter: bool = False,
    ) -> tuple[object, object]: ...


_MODEL: _FasterWhisper | None = None
_MODEL_DIR: Path | None = None


def resolve_whisper_dir(settings: Settings) -> Path | None:
    """Pinned dir, then Hugging Face hub snapshots already on this machine."""
    configured = Path(settings.asr_whisper_model_path.strip())
    if _is_whisper_dir(configured):
        return configured
    bench = settings.bench_whisper_model.strip()
    if bench:
        named = Path(bench)
        if _is_whisper_dir(named):
            return named
        if named.is_file() and named.name == "model.bin" and _is_whisper_dir(named.parent):
            return named.parent
    found = find_cached_whisper()
    if found is not None:
        return found
    return None


def find_cached_whisper() -> Path | None:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    for repo in _HF_REPOS:
        snaps = hub / repo / "snapshots"
        if not snaps.is_dir():
            continue
        for snap in sorted(snaps.iterdir()):
            if _is_whisper_dir(snap):
                return snap
    return None


def _is_whisper_dir(path: Path) -> bool:
    return path.is_dir() and (path / "model.bin").is_file() and (path / "config.json").is_file()


def install_whisper_tiny_en(dest: Path, *, timeout_s: int = 300) -> Path:
    """Copy a cached snapshot or download Systran/faster-whisper-tiny.en."""
    if _is_whisper_dir(dest):
        return dest
    cached = find_cached_whisper()
    if cached is not None:
        dest.mkdir(parents=True, exist_ok=True)
        for item in cached.iterdir():
            if item.is_file():
                shutil.copy2(item, dest / item.name)
        if not _is_whisper_dir(dest):
            raise FileNotFoundError(f"cached whisper snapshot incomplete: {cached}")
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    for name in _WHISPER_FILES:
        url = f"{_TINY_EN_BASE}/{name}?download=true"
        request = urllib.request.Request(url, headers={"User-Agent": "turnwise-download/0.1"})
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = response.read()
        (dest / name).write_bytes(payload)
    if not _is_whisper_dir(dest):
        raise FileNotFoundError(f"whisper download incomplete: {dest}")
    return dest


def whisper_unavailable_reason(settings: Settings) -> str | None:
    import importlib.util

    if importlib.util.find_spec("faster_whisper") is None:
        return "import_faster_whisper"
    if resolve_whisper_dir(settings) is None:
        return "weights_unpinned"
    return None


def _whisper_model(model_dir: Path) -> _FasterWhisper:
    global _MODEL, _MODEL_DIR
    if _MODEL is not None and model_dir == _MODEL_DIR:
        return _MODEL
    from faster_whisper import WhisperModel

    _MODEL = cast(_FasterWhisper, WhisperModel(str(model_dir), device="cpu", compute_type="int8"))
    _MODEL_DIR = model_dir
    return _MODEL


def transcribe_pcm16(
    pcm: bytes,
    sample_rate: int,
    *,
    model_dir: Path,
    dst_hz: int = 16000,
) -> tuple[str, float]:
    """Decode one utterance. Elapsed is full-file decode, not a streaming drain."""
    audio = _pcm16_to_float32(pcm, sample_rate, dst_hz)
    loaded = _whisper_model(model_dir)
    started = time.perf_counter()
    segments, _info = loaded.transcribe(audio, language="en", beam_size=1, vad_filter=False)
    text = " ".join(segment.text.strip() for segment in _segments(segments)).strip()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return text, elapsed_ms


def local_agreement_delay_ms(
    pcm: bytes,
    sample_rate: int,
    *,
    model_dir: Path,
    dst_hz: int = 16000,
    window_ms: int = 500,
) -> tuple[str, float, str]:
    """Prefix-decode overlapping windows. Delay is time after the last window to a stable prefix."""
    audio = _pcm16_to_float32(pcm, sample_rate, dst_hz)
    loaded = _whisper_model(model_dir)
    hop = max(1, int(dst_hz * window_ms / 1000))
    agreement = LocalAgreement2()
    last_text = ""
    stable = ""
    delay_ms = 0.0
    end = hop
    while True:
        chunk = audio[: min(end, audio.shape[0])]
        last = end >= audio.shape[0]
        started = time.perf_counter()
        segments, _info = loaded.transcribe(chunk, language="en", beam_size=1, vad_filter=False)
        last_text = " ".join(segment.text.strip() for segment in _segments(segments)).strip()
        stable = agreement.push(last_text).strip()
        if last:
            delay_ms = (time.perf_counter() - started) * 1000.0
            break
        end = min(audio.shape[0], end + hop)
    return last_text, delay_ms, stable


def _segments(raw: object) -> list[_WhisperSegment]:
    return list(cast(Iterable[_WhisperSegment], raw))


def _pcm16_to_float32(pcm: bytes, src_hz: int, dst_hz: int) -> NDArray[np.float32]:
    if src_hz != dst_hz:
        pcm = resample_mono_pcm16(pcm, src_hz, dst_hz)
    if len(pcm) % 2 != 0:
        raise ValueError("whisper pcm length must be even")
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
