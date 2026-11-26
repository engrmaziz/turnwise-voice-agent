"""Utterance emotion scorer. Stub returns None until ADR-011 flips the flag."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import structlog

from nlp.fusion import EmotionProbs

_LOG = structlog.get_logger("models.emotion_pool")

EmotionFn = Callable[[bytes], EmotionProbs | None]


class EmotionScorer:
    """Process-wide 3-class scorer. Timeouts and missing weights are ``None``."""

    def __init__(
        self,
        *,
        available: bool,
        timeout_s: float,
        infer_sync: EmotionFn | None = None,
        executor: ThreadPoolExecutor | None = None,
        model_name: str = "unavailable",
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self.available = available
        self.model_name = model_name
        self._timeout_s = timeout_s
        self._infer_sync = infer_sync
        self._owns_executor = executor is None
        self._executor = (
            executor
            if executor is not None
            else ThreadPoolExecutor(max_workers=1, thread_name_prefix="emotion")
        )

    @classmethod
    def fixed(
        cls,
        probs: EmotionProbs,
        *,
        timeout_ms: int,
        sleep_s: float = 0.0,
    ) -> EmotionScorer:
        def infer_sync(_pcm: bytes) -> EmotionProbs | None:
            if sleep_s > 0:
                import time

                time.sleep(sleep_s)
            return probs

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name="fixed",
        )

    @classmethod
    def stub(cls, *, timeout_ms: int, sleep_s: float = 0.0) -> EmotionScorer:
        def infer_sync(_pcm: bytes) -> EmotionProbs | None:
            if sleep_s > 0:
                import time

                time.sleep(sleep_s)
            return None

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name="stub",
        )

    @classmethod
    def load(cls, path: Path, *, timeout_ms: int) -> EmotionScorer:
        if not path.is_file():
            raise FileNotFoundError(str(path))
        # T8.1.3 did not export weights. A file on disk is not a 3-class contract.
        # Scoring stays None until export.py writes a real ONNX and ADR-011 flips.
        _LOG.warning("emotion_onnx_unwired", path=str(path))
        loaded = cls.stub(timeout_ms=timeout_ms)
        loaded.model_name = path.name
        return loaded

    async def score(self, pcm: bytes, generation: int) -> EmotionProbs | None:
        if not self.available or self._infer_sync is None:
            return None
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._infer_sync, pcm),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            _LOG.warning("emotion_timeout", timeout_s=self._timeout_s)
            raise
        if result is None:
            return None
        return result.model_copy(update={"generation": generation})

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False)
