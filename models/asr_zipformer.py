"""CPU Zipformer via sherpa-onnx. Import happens at load, not at module import."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from models.asr_types import AsrHypothesis, WordConf


class _SherpaStream(Protocol):
    def accept_waveform(self, sample_rate: int, samples: NDArray[np.float32]) -> None: ...

    def input_finished(self) -> None: ...


class ZipformerRecognizer(Protocol):
    def create_stream(self, hotwords: str | None = None) -> _SherpaStream: ...

    def is_ready(self, stream: _SherpaStream) -> bool: ...

    def decode_stream(self, stream: _SherpaStream) -> None: ...

    def get_result(self, stream: _SherpaStream) -> object: ...


def pcm16_to_float32(pcm: bytes) -> NDArray[np.float32]:
    if len(pcm) % 2 != 0:
        raise ValueError("asr pcm length must be even")
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def load_zipformer_recognizer(
    *,
    encoder: Path,
    decoder: Path,
    joiner: Path,
    tokens: Path,
    sample_rate: int,
    hotword_score: float,
) -> ZipformerRecognizer:
    import sherpa_onnx

    loaded = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(tokens),
        encoder=str(encoder),
        decoder=str(decoder),
        joiner=str(joiner),
        num_threads=1,
        sample_rate=int(sample_rate),
        feature_dim=80,
        decoding_method="greedy_search",
        enable_endpoint_detection=False,
        hotwords_score=hotword_score,
        model_type="zipformer2",
        provider="cpu",
    )
    return cast(ZipformerRecognizer, loaded)


def warmup_recognizer(recognizer: ZipformerRecognizer, sample_rate: int) -> None:
    """ORT init belongs on load, not on the first caller frame."""
    stream = recognizer.create_stream()
    silence = np.zeros(sample_rate, dtype=np.float32)
    stream.accept_waveform(sample_rate, silence)
    stream.input_finished()
    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)
    recognizer.get_result(stream)


def decode_utterance(
    recognizer: ZipformerRecognizer,
    pcm: bytes,
    sample_rate: int,
    *,
    generation: int = 0,
    hotwords: tuple[str, ...] = (),
) -> tuple[AsrHypothesis, float]:
    """Stream pcm, then time the post-audio drain. Drain is finalize, not RTF."""
    utterance = ZipformerUtterance(
        recognizer=recognizer,
        generation=generation,
        sample_rate=sample_rate,
        hotwords=hotwords,
    )
    frame = sample_rate * 2 // 50
    for offset in range(0, len(pcm), frame):
        utterance.push(pcm[offset : offset + frame])
    started = time.perf_counter()
    final = utterance.finish()
    drain_ms = (time.perf_counter() - started) * 1000.0
    return final, drain_ms


@dataclass(slots=True)
class ZipformerUtterance:
    recognizer: ZipformerRecognizer
    generation: int
    sample_rate: int
    hotwords: tuple[str, ...] = ()
    _stream: _SherpaStream | None = field(default=None, repr=False)

    def set_hotwords(self, words: tuple[str, ...]) -> None:
        self.hotwords = words
        self._stream = None

    def push(self, pcm: bytes) -> AsrHypothesis:
        stream = self._ensure_stream()
        samples = pcm16_to_float32(pcm)
        stream.accept_waveform(self.sample_rate, samples)
        self._decode(stream)
        text = str(self.recognizer.get_result(stream))
        return _hypothesis(text, self.generation, is_final=False)

    def finish(self) -> AsrHypothesis:
        stream = self._ensure_stream()
        tail = np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)
        stream.accept_waveform(self.sample_rate, tail)
        stream.input_finished()
        self._decode(stream)
        text = str(self.recognizer.get_result(stream))
        return _hypothesis(text, self.generation, is_final=True)

    def _ensure_stream(self) -> _SherpaStream:
        if self._stream is None:
            # Greedy zipformer has no hotword API. Passing phrases to
            # create_stream aborts inside sherpa-onnx (beam-search only).
            self._stream = self.recognizer.create_stream()
        return self._stream

    def _decode(self, stream: _SherpaStream) -> None:
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)


def _hypothesis(text: str, generation: int, *, is_final: bool) -> AsrHypothesis:
    stripped = text.strip()
    words = tuple(
        WordConf(text=token, start_ms=0, end_ms=0, confidence=None) for token in stripped.split()
    )
    return AsrHypothesis(
        text=stripped,
        words=words,
        stable_prefix=stripped,
        generation=generation,
        is_final=is_final,
    )
