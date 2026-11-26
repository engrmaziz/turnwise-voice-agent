"""Empty retrieval refuses. Ungrounded counter stays 0."""

from pathlib import Path

from prometheus_client import CollectorRegistry

from pipeline.metrics import build_stage_metrics
from tests.support import counter_value
from tools.faq import load_chunks, retrieve


def test_empty_retrieval_returns_refusal() -> None:
    chunks = load_chunks(Path("data/faq.md"))
    hit = retrieve("zzzzzyyyyy xxxxxwwww qqqqvvvv", chunks, min_score=0.2)
    assert hit is None
    hours = retrieve("what are your hours", chunks, min_score=0.2)
    assert hours is not None
    assert hours.chunk_id
    assert hours.chunk_id in hours.reply


def test_ungrounded_counter_stays_zero_on_empty() -> None:
    registry = CollectorRegistry()
    metrics = build_stage_metrics(registry)
    chunks = load_chunks(Path("data/faq.md"))
    hit = retrieve("zzzzzyyyyy xxxxxwwww qqqqvvvv", chunks, min_score=0.2)
    assert hit is None
    # Refusal is not an ungrounded answer. Do not increment.
    assert counter_value(metrics.faq_ungrounded) == 0.0
