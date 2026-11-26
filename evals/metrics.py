"""Eval metric formulas. Tiny-fixture p50 uses the even-n midpoint, not a histogram."""

from __future__ import annotations

import math
from collections.abc import Sequence

from evals.judge_db import DbJudgement

ESTIMATOR = "midpoint_even_nearest_rank_odd"


def percentile(values: Sequence[float], p: float) -> float:
    """p50 on even n is the midpoint of the two central values. Documented estimator.

    Do not mix this number with a Prometheus histogram quantile in the same table
    without an ``estimator`` column.
    """
    if not values:
        raise ValueError("percentile needs samples")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    xs = sorted(values)
    if p == 50 and len(xs) % 2 == 0:
        mid = len(xs) // 2
        return (xs[mid - 1] + xs[mid]) / 2.0
    rank = max(1, math.ceil(p / 100.0 * len(xs)))
    return xs[rank - 1]


def task_success(judgements: Sequence[DbJudgement]) -> float:
    if not judgements:
        raise ValueError("task_success needs judgements")
    hits = sum(1 for item in judgements if item.success)
    return hits / len(judgements)


def urgent_recall(states: Sequence[str], urgent: Sequence[bool]) -> float:
    if len(states) != len(urgent):
        raise ValueError("lists must align")
    marked = [state for state, flag in zip(states, urgent, strict=True) if flag]
    if not marked:
        raise ValueError("no urgent scenarios")
    return sum(state == "URGENT" for state in marked) / len(marked)


def false_urgent(states: Sequence[str], urgent: Sequence[bool]) -> float:
    if len(states) != len(urgent):
        raise ValueError("lists must align")
    other = [state for state, flag in zip(states, urgent, strict=True) if not flag]
    if not other:
        return 0.0
    return sum(state == "URGENT" for state in other) / len(other)


def faq_hallucination(ungrounded: int, faq_says: int) -> float:
    if faq_says <= 0:
        return 0.0
    return ungrounded / faq_says
