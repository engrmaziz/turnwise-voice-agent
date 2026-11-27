"""LLM client. Structured output is grammar-constrained JSON, never regex-scraped."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from models.llm_ollama import OllamaError
from models.llm_ollama import generate as ollama_generate

_LOG = structlog.get_logger("models.llm_client")

QueueWait = Callable[[float], None]
LlmFn = Callable[[str, type[BaseModel] | None], str]


class LlmGrammarError(Exception):
    """Model output was not valid JSON for the requested schema."""


class LlmTimeoutError(Exception):
    """The client exceeded llm_timeout_ms."""


class _Ping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


class ProposalSchema(BaseModel):
    """Closed proposal object. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    slots: dict[str, str]


_Job = tuple[int, int, asyncio.Future[str], str, float, type[BaseModel] | None]


@dataclass(slots=True)
class LlmClient:
    """Process-wide client. Missing binaries use the stub path.

    Speaking sessions enqueue at priority 0. Idle jobs wait behind them.
    ``max_batch`` is the worker cap (strategy C).
    """

    timeout_s: float
    complete_sync: LlmFn | None
    available: bool
    model_name: str = "unavailable"
    max_batch: int = 1
    queue_wait_observe: QueueWait | None = None
    _hold: bool = False
    _queue: asyncio.PriorityQueue[_Job] | None = field(default=None, repr=False)
    _seq: int = 0
    _tasks: list[asyncio.Task[None]] = field(default_factory=list, repr=False)
    _workers: int = 0

    @classmethod
    def unavailable(cls, *, timeout_ms: int, max_batch: int = 1) -> LlmClient:
        return cls(
            timeout_s=timeout_ms / 1000.0,
            complete_sync=None,
            available=False,
            max_batch=max(1, max_batch),
        )

    @classmethod
    def stub(
        cls,
        *,
        timeout_ms: int,
        response: str,
        sleep_s: float = 0.0,
        max_batch: int = 1,
    ) -> LlmClient:
        def complete_sync(_prompt: str, _schema: type[BaseModel] | None = None) -> str:
            if sleep_s > 0:
                time.sleep(sleep_s)
            return response

        return cls(
            timeout_s=timeout_ms / 1000.0,
            complete_sync=complete_sync,
            available=True,
            model_name="stub",
            max_batch=max(1, max_batch),
        )

    @classmethod
    def ollama(
        cls,
        *,
        host: str,
        model: str,
        timeout_ms: int,
        max_batch: int = 1,
    ) -> LlmClient:
        timeout_s = timeout_ms / 1000.0

        def complete_sync(prompt: str, schema: type[BaseModel] | None = None) -> str:
            return ollama_generate(
                host,
                model,
                prompt,
                timeout_s=timeout_s,
                schema=schema,
            )

        try:
            ollama_generate(
                host,
                model,
                'Reply with {"ok": true}.',
                timeout_s=max(timeout_s, 30.0),
                schema=_Ping,
            )
        except OllamaError as exc:
            raise FileNotFoundError(f"ollama warmup failed: {exc}") from exc
        return cls(
            timeout_s=timeout_s,
            complete_sync=complete_sync,
            available=True,
            model_name=f"ollama:{model}",
            max_batch=max(1, max_batch),
        )

    async def complete_json(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        speaking: bool = False,
    ) -> dict[str, Any]:
        if not self.available or self.complete_sync is None:
            raise LlmGrammarError("llm unavailable")
        queued = time.perf_counter()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        queue = self._ensure_queue()
        self._seq += 1
        priority = 0 if speaking else 1
        await queue.put((priority, self._seq, future, prompt, queued, schema))
        self._ensure_workers()
        try:
            raw = await asyncio.wait_for(future, timeout=self.timeout_s)
        except TimeoutError as exc:
            if not future.done():
                future.cancel()
            _LOG.warning("llm_timeout", timeout_s=self.timeout_s)
            raise LlmTimeoutError("llm timeout") from exc
        return parse_grammar(raw, schema)

    def hold_dispatch(self) -> None:
        """Keep jobs queued. Tests use this so a speaking job can cut the line."""
        self._hold = True

    def release_dispatch(self) -> None:
        self._hold = False
        self._ensure_workers()

    def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        self._workers = 0

    def _ensure_queue(self) -> asyncio.PriorityQueue[_Job]:
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()
        return self._queue

    def _ensure_workers(self) -> None:
        if self._hold:
            return
        cap = max(1, self.max_batch)
        while self._workers < cap:
            self._workers += 1
            task = asyncio.create_task(self._worker(), name="llm-worker")
            self._tasks.append(task)

    async def _worker(self) -> None:
        queue = self._ensure_queue()
        loop = asyncio.get_running_loop()
        while True:
            _priority, _seq, future, prompt, queued, schema = await queue.get()
            waited = time.perf_counter() - queued
            observe = self.queue_wait_observe
            if observe is not None:
                observe(waited)
            if future.cancelled():
                queue.task_done()
                continue
            sync = self.complete_sync
            if sync is None:
                if not future.done():
                    future.set_exception(LlmGrammarError("llm unavailable"))
                queue.task_done()
                continue
            try:
                raw = await loop.run_in_executor(None, partial(sync, prompt, schema))
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
            else:
                if not future.done():
                    future.set_result(raw)
            queue.task_done()


def parse_grammar(raw: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Typed error on non-JSON. No regex scrape of free text."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmGrammarError("non-json") from exc
    try:
        parsed = schema.model_validate(payload)
    except ValidationError as exc:
        raise LlmGrammarError("schema") from exc
    return parsed.model_dump()
