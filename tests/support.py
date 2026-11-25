"""Helpers shared by foundation tests."""

from prometheus_client import Counter, Histogram


def counter_value(counter: Counter, **labels: str) -> float:
    found = 0.0
    seen = False
    for family in counter.collect():
        for sample in family.samples:
            if not sample.name.endswith("_total"):
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                found = float(sample.value)
                seen = True
    if not seen:
        return 0.0
    return found


def histogram_count(histogram: Histogram, **labels: str) -> float:
    for family in histogram.collect():
        for sample in family.samples:
            if not sample.name.endswith("_count"):
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0
