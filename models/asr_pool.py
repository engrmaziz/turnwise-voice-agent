"""Process-wide ASR worker pool. Inference runs in an executor, never on the loop."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import structlog

from models.asr_types import AsrHypothesis, WordConf
from nlp.local_agreement import LocalAgreement2
from pipeline.metrics import StageMetrics
from server.config import Settings

_LOG = structlog.get_logger("models.asr_pool")

LiveGeneration = Callable[[], int]
SpeakingFlag = Callable[[], bool]


class AsrBackendError(Exception):
    """Real backend cannot start. Empty ``asr_backend`` is this error."""


@dataclass(slots=True)
class _Job:
    priority: int
    seq: int
    generation: int
    live: LiveGeneration
    fn: Callable[[], AsrHypothesis]
    future: asyncio.Future[AsrHypothesis | None]


class AsrStream:
    """One utterance. ``push`` and ``finish`` go through the pool scheduler."""

    def __init__(
        self,
        *,
        pool: AsrPool,
        session_id: str,
        generation: int,
        live: LiveGeneration,
        speaking: SpeakingFlag,
        transcript: str,
        sleep_s: float,
        supports_hotwords: bool,
    ) -> None:
        self.session_id = session_id
        self.generation = generation
        self.supports_hotwords = supports_hotwords
        self.hotwords: tuple[str, ...] = ()
        self.hotword_score = 0.0
        self._pool = pool
        self._live = live
        self._speaking = speaking
        self._transcript = transcript
        self._sleep_s = sleep_s
        self._pcm = bytearray()
        self._agreement = LocalAgreement2()
        self._finished = False

    def set_hotwords(self, words: Sequence[str], score: float) -> None:
        self.hotwords = tuple(words)
        self.hotword_score = score

    async def push(self, pcm: bytes) -> AsrHypothesis | None:
        if self._finished:
            raise RuntimeError("push after finish")
        if len(pcm) % 2 != 0:
            raise ValueError("asr pcm length must be even")
        captured = bytes(pcm)
        return await self._pool.submit(
            lambda: self._push_sync(captured),
            generation=self.generation,
            live=self._live,
            speaking=self._speaking(),
        )

    async def finish(self) -> AsrHypothesis | None:
        if self._finished:
            raise RuntimeError("finish called twice")
        self._finished = True
        return await self._pool.submit(
            self._finish_sync,
            generation=self.generation,
            live=self._live,
            speaking=self._speaking(),
        )

    def _push_sync(self, pcm: bytes) -> AsrHypothesis:
        if self._sleep_s > 0:
            time.sleep(self._sleep_s)
        self._pcm.extend(pcm)
        text = self._visible()
        stable = self._agreement.push(text)
        return AsrHypothesis(
            text=text,
            words=_words_without_scores(text),
            stable_prefix=stable,
            generation=self.generation,
            is_final=False,
        )

    def _finish_sync(self) -> AsrHypothesis:
        if self._sleep_s > 0:
            time.sleep(self._sleep_s)
        text = self._transcript
        return AsrHypothesis(
            text=text,
            words=_words_without_scores(text),
            stable_prefix=text,
            generation=self.generation,
            is_final=True,
        )

    def _visible(self) -> str:
        words = self._transcript.split()
        if not words:
            return ""
        # One 20 ms 16 kHz frame is 640 bytes. A word appears after ~5 frames.
        revealed = max(1, len(self._pcm) // (640 * 5))
        return " ".join(words[: min(len(words), revealed)])


class AsrPool:
    """Shared slots. Speaking sessions are dequeued before idle ones."""

    def __init__(
        self,
        *,
        slots: int,
        timeout_s: float,
        metrics: StageMetrics,
        transcript: str,
        sleep_s: float = 0.0,
        backend: str = "stub",
        supports_hotwords: bool = False,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        if slots < 1:
            raise ValueError("slots must be >= 1")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self.backend = backend
        self.supports_hotwords = supports_hotwords
        self._timeout_s = timeout_s
        self._metrics = metrics
        self._transcript = transcript
        self._sleep_s = sleep_s
        if executor is None:
            self._owns_executor = True
            self._executor = ThreadPoolExecutor(max_workers=slots, thread_name_prefix="asr")
        else:
            self._owns_executor = False
            self._executor = executor
        self._seq = 0
        self._queue: asyncio.PriorityQueue[tuple[int, int]] | None = None
        self._jobs: dict[int, _Job] = {}
        self._worker: asyncio.Task[None] | None = None

    @classmethod
    def stub(cls, settings: Settings, metrics: StageMetrics, *, sleep_s: float = 0.0) -> AsrPool:
        return cls(
            slots=settings.asr_pool_slots,
            timeout_s=settings.asr_finish_timeout_ms / 1000.0,
            metrics=metrics,
            transcript=settings.asr_stub_transcript,
            sleep_s=sleep_s,
            backend="stub",
            supports_hotwords=True,
        )

    @classmethod
    def load_real(cls, settings: Settings, metrics: StageMetrics) -> AsrPool:
        """Refuse empty backend. Missing weights fail here, not on the first caller."""
        backend = settings.asr_backend.strip()
        if backend == "":
            raise AsrBackendError("asr_backend is empty")
        if backend == "stub":
            return cls.stub(settings, metrics)
        if backend not in {"zipformer", "whisper_la2"}:
            raise AsrBackendError(f"unknown asr_backend {backend}")
        raise FileNotFoundError(f"asr backend {backend} weights are not pinned")

    def start_stream(
        self,
        session_id: str,
        generation: int,
        *,
        live: LiveGeneration,
        speaking: SpeakingFlag,
    ) -> AsrStream:
        self._ensure_worker()
        return AsrStream(
            pool=self,
            session_id=session_id,
            generation=generation,
            live=live,
            speaking=speaking,
            transcript=self._transcript,
            sleep_s=self._sleep_s,
            supports_hotwords=self.supports_hotwords,
        )

    async def submit(
        self,
        fn: Callable[[], AsrHypothesis],
        *,
        generation: int,
        live: LiveGeneration,
        speaking: bool,
    ) -> AsrHypothesis | None:
        self._ensure_worker()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[AsrHypothesis | None] = loop.create_future()
        self._seq += 1
        seq = self._seq
        job = _Job(
            priority=0 if speaking else 1,
            seq=seq,
            generation=generation,
            live=live,
            fn=fn,
            future=future,
        )
        self._jobs[seq] = job
        assert self._queue is not None
        await self._queue.put((job.priority, seq))
        try:
            return await asyncio.wait_for(future, timeout=self._timeout_s)
        except TimeoutError:
            _LOG.warning("asr_timeout", timeout_s=self._timeout_s, session_generation=generation)
            future.cancel()
            raise

    def close(self) -> None:
        worker = self._worker
        if worker is not None and not worker.done():
            worker.cancel()
        self._worker = None
        if self._owns_executor:
            self._executor.shutdown(wait=False)

    def _ensure_worker(self) -> None:
        loop = asyncio.get_running_loop()
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()
        if self._worker is None or self._worker.done():
            self._worker = loop.create_task(self._run(), name="asr-pool")

    async def _run(self) -> None:
        assert self._queue is not None
        try:
            while True:
                _priority, seq = await self._queue.get()
                job = self._jobs.pop(seq, None)
                if job is None or job.future.done():
                    continue
                try:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(self._executor, job.fn)
                except Exception as exc:
                    if not job.future.done():
                        job.future.set_exception(exc)
                    continue
                if job.live() != job.generation:
                    self._metrics.asr_dropped_generation.inc()
                    if not job.future.done():
                        job.future.set_result(None)
                    continue
                if not job.future.done():
                    job.future.set_result(result)
        except asyncio.CancelledError:
            return


def _words_without_scores(text: str) -> tuple[WordConf, ...]:
    """Stub has no word scores. Slot confidence later treats missing as 0.0."""
    return tuple(
        WordConf(text=token, start_ms=0, end_ms=0, confidence=None) for token in text.split()
    )
