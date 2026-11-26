"""ASR hypothesis types. Shared by the pool and spoken-form NLP."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WordConf:
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class AsrHypothesis:
    text: str
    words: tuple[WordConf, ...]
    stable_prefix: str
    generation: int
    is_final: bool = False
