"""Measure one bus hop. The median is a regression guard, not a TTFA claim."""

import asyncio
import logging
import platform
import statistics
import time

from pipeline.event import Event, EventKind
from tests.conftest import Harness
from tests.support import histogram_count

_WARMUP = 20
_SAMPLES = 200
_CEILING_MS = 5.0
_LOG = logging.getLogger("turnwise.bench")


async def test_stage_hop_median_stays_under_the_ceiling(harness: Harness) -> None:
    latencies_ms: list[float] = []
    gate = asyncio.Event()

    async def handler(event: Event) -> None:
        started = event.payload["t0"]
        assert isinstance(started, float)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        gate.set()

    stage = harness.stage("hop", handler)
    stage.start()
    total = _WARMUP + _SAMPLES
    for _ in range(total):
        gate.clear()
        event = harness.session.create_event(EventKind.PARTIAL, {"t0": time.perf_counter()})
        await stage.emit(event)
        await gate.wait()
    measured = latencies_ms[_WARMUP:]
    median_ms = statistics.median(measured)
    _LOG.warning(
        "stage_hop_median_ms=%.4f samples=%d python=%s platform=%s",
        median_ms,
        len(measured),
        platform.python_version(),
        platform.platform(),
    )
    assert histogram_count(harness.metrics.latency, stage="hop") == float(total)
    assert median_ms < _CEILING_MS
    await stage.aclose()
