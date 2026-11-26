"""Joint intent + BIO scorer. Inference is in an executor with a hard timeout."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import structlog

from nlp.nlu_features import FEATURE_DIM, NGRAM, intent_features, token_features, tokenize
from nlp.nlu_vocab import BIO_TAGS, INTENTS

_LOG = structlog.get_logger("models.nlu_pool")

NluFn = Callable[[str], "NluHypothesis"]


@dataclass(frozen=True, slots=True)
class NluHypothesis:
    intent: str
    intent_confidence: float
    tokens: tuple[str, ...]
    tags: tuple[str, ...]


class NluUnavailableError(Exception):
    """Weights missing."""


class NluScorer:
    """Process-wide NLU. One encoder conceptually; two linear ONNX heads here."""

    def __init__(
        self,
        *,
        available: bool,
        timeout_s: float,
        infer_sync: NluFn | None = None,
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
            else ThreadPoolExecutor(max_workers=1, thread_name_prefix="nlu")
        )

    @classmethod
    def unavailable(cls, *, timeout_ms: int) -> NluScorer:
        return cls(available=False, timeout_s=timeout_ms / 1000.0, model_name="unavailable")

    @classmethod
    def stub(
        cls,
        *,
        timeout_ms: int,
        hypothesis: NluHypothesis,
        sleep_s: float = 0.0,
    ) -> NluScorer:
        def infer_sync(_text: str) -> NluHypothesis:
            if sleep_s > 0:
                import time

                time.sleep(sleep_s)
            return hypothesis

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name="stub",
        )

    @classmethod
    def load(
        cls,
        intent_path: Path,
        bio_path: Path,
        *,
        timeout_ms: int,
        feature_dim: int = FEATURE_DIM,
        ngram: int = NGRAM,
    ) -> NluScorer:
        if not intent_path.is_file() or not bio_path.is_file():
            raise FileNotFoundError("nlu onnx missing")
        import numpy as np
        import onnxruntime as ort

        intent_sess = ort.InferenceSession(str(intent_path), providers=["CPUExecutionProvider"])
        bio_sess = ort.InferenceSession(str(bio_path), providers=["CPUExecutionProvider"])
        intent_in = intent_sess.get_inputs()[0].name
        bio_in = bio_sess.get_inputs()[0].name

        def infer_sync(text: str) -> NluHypothesis:
            x = np.asarray(
                [intent_features(text, dim=feature_dim, ngram=ngram)], dtype=np.float32
            )
            intent_out = np.ravel(intent_sess.run(None, {intent_in: x})[0])
            intent_i = int(np.argmax(intent_out))
            tokens = tokenize(text)
            tags: list[str] = []
            for index in range(len(tokens)):
                tx = np.asarray(
                    [token_features(tokens, index, dim=feature_dim, ngram=ngram)],
                    dtype=np.float32,
                )
                bio_out = np.ravel(bio_sess.run(None, {bio_in: tx})[0])
                tags.append(BIO_TAGS[int(np.argmax(bio_out))])
            return NluHypothesis(
                intent=INTENTS[intent_i],
                intent_confidence=float(intent_out[intent_i]),
                tokens=tuple(tokens),
                tags=tuple(tags),
            )

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            model_name=intent_path.name,
        )

    @property
    def infer_sync(self) -> NluFn | None:
        return self._infer_sync

    async def predict(self, text: str) -> NluHypothesis:
        if not self.available or self._infer_sync is None:
            raise NluUnavailableError("nlu onnx missing")
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._infer_sync, text),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            _LOG.warning("nlu_timeout", timeout_s=self._timeout_s)
            raise

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False)
