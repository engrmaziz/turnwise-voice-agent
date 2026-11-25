"""Process-wide Silero VAD. Inference runs in an executor, never on the loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog

_LOG = structlog.get_logger("models.vad_pool")

InferFn = Callable[[bytes, object, int], "VadInference"]
StateFn = Callable[[], object]


class VadUnavailableError(Exception):
    """ONNX file missing. The stage uses the energy gate without waiting."""


@dataclass(frozen=True, slots=True)
class VadInference:
    probability: float
    state: object
    generation: int


class VadEngine(Protocol):
    """Injected into the VAD stage. Production implementation is ``VadPool``."""

    available: bool
    model_name: str
    opset: int | None

    def new_state(self) -> object: ...

    async def infer(self, pcm16: bytes, state: object, generation: int) -> VadInference: ...

    def close(self) -> None: ...


class VadPool:
    """One ONNX session for the process. RNN state is per call, passed in."""

    def __init__(
        self,
        *,
        available: bool,
        timeout_s: float,
        infer_sync: InferFn | None = None,
        new_state: StateFn | None = None,
        executor: ThreadPoolExecutor | None = None,
        model_name: str = "none",
        opset: int | None = None,
        path: Path | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self.available = available
        self.model_name = model_name
        self.opset = opset
        self.path = path
        self._timeout_s = timeout_s
        self._infer_sync = infer_sync
        self._new_state = new_state
        self._owns_executor = executor is None
        self._executor = (
            executor
            if executor is not None
            else ThreadPoolExecutor(max_workers=1, thread_name_prefix="vad")
        )

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        timeout_ms: int,
        window_samples: int,
        sample_rate_hz: int,
        executor: ThreadPoolExecutor | None = None,
    ) -> VadPool:
        """Load ONNX at construction. A missing or corrupt file fails here."""
        if not path.is_file():
            raise FileNotFoundError(str(path))
        import numpy as np
        import onnxruntime as ort

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        input_names = [item.name for item in session.get_inputs()]
        if not input_names:
            raise ValueError(f"onnx {path} has no inputs")
        audio_name = input_names[0]
        state_name = next((name for name in input_names[1:] if name != "sr"), None)
        sr_name = "sr" if "sr" in input_names else None
        state_spec = next((item for item in session.get_inputs() if item.name == state_name), None)
        state_shape = _concrete_shape(
            tuple(state_spec.shape) if state_spec is not None else (2, 1, 128)
        )

        def infer_sync(pcm16: bytes, state: object, generation: int) -> VadInference:
            samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
            if samples.size != window_samples:
                raise ValueError("vad window sample count mismatch")
            feeds: dict[str, object] = {audio_name: samples.reshape(1, -1)}
            if state_name is not None:
                feeds[state_name] = state
            if sr_name is not None:
                feeds[sr_name] = np.array(sample_rate_hz, dtype=np.int64)
            outputs = session.run(None, feeds)
            probability = float(np.ravel(outputs[0])[0])
            next_state: object = outputs[1] if len(outputs) > 1 else state
            return VadInference(probability=probability, state=next_state, generation=generation)

        def make_state() -> object:
            return np.zeros(state_shape, dtype=np.float32)

        return cls(
            available=True,
            timeout_s=timeout_ms / 1000.0,
            infer_sync=infer_sync,
            new_state=make_state,
            executor=executor,
            model_name=path.name,
            opset=_opset_from_ir(session),
            path=path,
        )

    @classmethod
    def unavailable(cls, *, timeout_ms: int) -> VadPool:
        return cls(available=False, timeout_s=timeout_ms / 1000.0, model_name="unavailable")

    def new_state(self) -> object:
        if self._new_state is None:
            return None
        return self._new_state()

    async def infer(self, pcm16: bytes, state: object, generation: int) -> VadInference:
        if not self.available or self._infer_sync is None:
            raise VadUnavailableError("silero onnx missing")
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._infer_sync, pcm16, state, generation),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            _LOG.warning("vad_timeout", timeout_s=self._timeout_s)
            raise

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False)


def _concrete_shape(shape: tuple[object, ...]) -> tuple[int, ...]:
    dims: list[int] = []
    for dim in shape:
        if isinstance(dim, int) and dim > 0:
            dims.append(dim)
        else:
            dims.append(1)
    return tuple(dims) if dims else (2, 1, 128)


def _opset_from_ir(session: object) -> int | None:
    getter = getattr(session, "get_session_options", None)
    if getter is None:
        return None
    try:
        options = getter()
    except Exception:
        return None
    ir_version = getattr(options, "graph_optimization_level", None)
    del ir_version
    return None
