"""Turn ONNX pool times out and the endpointer treats that as p_complete=0."""

import pytest

from models.onnx_pool import TurnScorer, TurnUnavailableError


async def test_unavailable_raises() -> None:
    scorer = TurnScorer.unavailable(timeout_ms=20)
    with pytest.raises(TurnUnavailableError):
        await scorer.p_complete("book tuesday", "none")
    scorer.close()


async def test_stub_timeout_raises() -> None:
    scorer = TurnScorer.stub(timeout_ms=20, score=1.0, sleep_s=0.2)
    with pytest.raises(TimeoutError):
        await scorer.p_complete("book tuesday", "none")
    scorer.close()


async def test_stub_score() -> None:
    scorer = TurnScorer.stub(timeout_ms=50, score=0.42)
    assert await scorer.p_complete("ok", "none") == pytest.approx(0.42)
    scorer.close()
