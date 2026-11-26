"""Process-wide TTS pool. Inference is in an executor; generation is stamped at submit."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

from pipeline.audio.format import resample_mono_pcm16
from server.config import Settings

_LOG = structlog.get_logger("models.tts_pool")

LiveGeneration = Callable[[], int]
SynthFn = Callable[[str, str, float], bytes]


class TtsError(Exception):
    """Synthesis failed or returned empty PCM."""


class TtsTimeoutError(TtsError):
    """The pool exceeded tts_timeout_ms."""


class TtsJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    generation: int
    text: str
    voice: str
    speed: float
    cache_key: str | None = None
    filler: int = 0
    first_chunk: bool = False


class TtsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pcm: bytes = Field(repr=False)
    generation: int
    cache_hit: bool
    latency_ms: float


@dataclass(slots=True)
class TtsPool:
    """Shared synthesizer. Empty backend uses the silence stub."""

    timeout_s: float
    synth_sync: SynthFn | None
    available: bool
    model_name: str = "unavailable"
    sample_rate_hz: int = 16000
    _executor: ThreadPoolExecutor | None = None
    _owns_executor: bool = False

    @classmethod
    def unavailable(cls, *, timeout_ms: int) -> TtsPool:
        return cls(timeout_s=timeout_ms / 1000.0, synth_sync=None, available=False)

    @classmethod
    def stub(
        cls,
        *,
        timeout_ms: int,
        frame_bytes: int,
        sleep_s: float = 0.0,
        pcm: bytes | None = None,
    ) -> TtsPool:
        def synth_sync(text: str, _voice: str, speed: float) -> bytes:
            if sleep_s > 0:
                time.sleep(sleep_s)
            if pcm is not None:
                if not pcm:
                    raise TtsError("empty pcm")
                return pcm
            words = max(1, len(text.split()))
            frames = max(1, round(words / max(speed, 0.01)))
            return b"\x00" * (frame_bytes * frames)

        return cls(
            timeout_s=timeout_ms / 1000.0,
            synth_sync=synth_sync,
            available=True,
            model_name="stub",
            _executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts"),
            _owns_executor=True,
        )

    @classmethod
    def piper(
        cls,
        *,
        onnx_path: Path,
        config_path: Path | None,
        timeout_ms: int,
        output_hz: int,
    ) -> TtsPool:
        """CPU Piper. Import and ONNX load happen here, not at module import."""
        from piper import PiperVoice, SynthesisConfig

        voice = PiperVoice.load(
            str(onnx_path),
            config_path=str(config_path) if config_path is not None else None,
            use_cuda=False,
        )
        src_hz = int(voice.config.sample_rate)
        base_length = float(voice.config.length_scale)

        def synth_sync(text: str, _voice: str, speed: float) -> bytes:
            stripped = text.strip()
            if not stripped:
                raise TtsError("empty pcm")
            length_scale = None if abs(speed - 1.0) < 1e-6 else base_length / max(speed, 0.01)
            syn_config = SynthesisConfig(length_scale=length_scale)
            chunks = list(voice.synthesize(stripped, syn_config=syn_config))
            if not chunks:
                raise TtsError("empty pcm")
            raw = b"".join(chunk.audio_int16_bytes for chunk in chunks)
            if not raw:
                raise TtsError("empty pcm")
            rate = int(chunks[0].sample_rate) if chunks[0].sample_rate else src_hz
            return resample_mono_pcm16(raw, rate, output_hz)

        return cls(
            timeout_s=timeout_ms / 1000.0,
            synth_sync=synth_sync,
            available=True,
            model_name=f"piper:{onnx_path.name}",
            sample_rate_hz=output_hz,
            _executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts-piper"),
            _owns_executor=True,
        )

    async def synthesize(
        self,
        job: TtsJob,
        *,
        live: LiveGeneration,
    ) -> TtsResult | None:
        if not self.available or self.synth_sync is None:
            raise TtsError("tts unavailable")
        stamped = job.generation
        loop = asyncio.get_running_loop()
        executor = self._executor
        started = time.perf_counter()
        try:
            pcm = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    self.synth_sync,
                    job.text,
                    job.voice,
                    job.speed,
                ),
                timeout=self.timeout_s,
            )
        except TimeoutError as exc:
            _LOG.warning("tts_timeout", timeout_s=self.timeout_s)
            raise TtsTimeoutError("tts timeout") from exc
        latency_ms = (time.perf_counter() - started) * 1000.0
        if live() != stamped:
            return None
        if not pcm:
            raise TtsError("empty pcm")
        return TtsResult(
            pcm=pcm,
            generation=stamped,
            cache_hit=False,
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        if self._owns_executor and self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None


def load_tts_pool(settings: Settings) -> TtsPool:
    backend = settings.tts_backend.strip()
    if backend in {"", "stub"}:
        return TtsPool.stub(
            timeout_ms=settings.tts_timeout_ms,
            frame_bytes=settings.tts_pcm_bytes,
        )
    if backend == "piper":
        return _load_piper(settings)
    return TtsPool.unavailable(timeout_ms=settings.tts_timeout_ms)


def _load_piper(settings: Settings) -> TtsPool:
    onnx = Path(settings.tts_piper_onnx_path)
    config_raw = settings.tts_piper_config_path.strip()
    config_path = Path(config_raw) if config_raw else None
    if not onnx.is_file():
        _LOG.warning("tts_piper_missing_onnx", path=str(onnx))
        return TtsPool.unavailable(timeout_ms=settings.tts_timeout_ms)
    if config_path is not None and not config_path.is_file():
        _LOG.warning("tts_piper_missing_config", path=str(config_path))
        return TtsPool.unavailable(timeout_ms=settings.tts_timeout_ms)
    try:
        return TtsPool.piper(
            onnx_path=onnx,
            config_path=config_path,
            timeout_ms=settings.tts_timeout_ms,
            output_hz=settings.ws_sample_rate_hz,
        )
    except ImportError:
        _LOG.warning("tts_piper_import_failed")
        return TtsPool.unavailable(timeout_ms=settings.tts_timeout_ms)
    except (OSError, ValueError, RuntimeError) as exc:
        _LOG.warning("tts_piper_load_failed", error=str(exc), path=str(onnx))
        return TtsPool.unavailable(timeout_ms=settings.tts_timeout_ms)
