"""Small ONNX scorers. Inference runs in an executor with a hard timeout."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import structlog

_LOG = structlog.get_logger("models.onnx_pool")

TurnFn = Callable[[str, str], float]


class TurnUnavailableError(Exception):
    """Weights missing or the model flag is off."""


class TurnScorer:
    """Process-wide turn-completion score in ``[0, 1]``."""

    def __init__(
        self,
        *,
        available: bool,
        timeout_s: float,
        infer_sync: TurnFn | None = None,
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
            else ThreadPoolExecutor(max_workers=1, thread_name_prefix="turn")
        )

    @classmethod
    def unavailable(cls, *, timeout_ms: int) -> TurnScorer:
        return cls(available=False, timeout_s=timeout_ms / 1000.0, model_name="unavailable")

    @classmethod
    def stub(cls, *, timeout_ms: int, score: float, sleep_s: float = 0.0) -> TurnScorer:
        def infer_sync(_text: str, _slot: str) -> float:
            if sleep_s > 0:
                import time

                time.sleep(sleep_s)
            return score

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name="stub",
        )

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        timeout_ms: int,
        feature_dim: int,
        ngram: int,
    ) -> TurnScorer:
        if not path.is_file():
            raise FileNotFoundError(str(path))
        import numpy as np
        import onnxruntime as ort

        from models.turn_features import hashed_vector

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name

        def infer_sync(text: str, slot: str) -> float:
            features = np.asarray(
                [hashed_vector(text, slot, dim=feature_dim, ngram=ngram)],
                dtype=np.float32,
            )
            outputs = session.run(None, {input_name: features})
            return float(np.ravel(outputs[0])[0])

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name=path.name,
        )

    async def p_complete(self, text: str, slot: str) -> float:
        if not self.available or self._infer_sync is None:
            raise TurnUnavailableError("turn onnx missing")
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._infer_sync, text, slot),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            _LOG.warning("turn_timeout", timeout_s=self._timeout_s)
            raise

    @property
    def infer_sync(self) -> TurnFn | None:
        return self._infer_sync

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False)
