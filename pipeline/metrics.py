"""Prometheus collectors for the stage runtime.

Counter *objects* are named without a ``_total`` suffix. The exposition format
adds ``_total``. Grafana queries must use the exported name.
"""

from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Stage hops are sub-millisecond to a few milliseconds. Later model stages share
# this histogram, so the buckets also cover hundreds of milliseconds.
_STAGE_BUCKETS = (
    0.001,
    0.0025,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
)

# 0.7 and 1.2 line up with the TTFA P50 and P95 targets so a quantile can sit
# on the SLO boundary. No samples are recorded until an audio-out stage exists.
_TTFA_BUCKETS = (0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.2, 2.0, 5.0)


@dataclass(slots=True)
class StageMetrics:
    """Collectors shared by every stage in one process."""

    latency: Histogram
    queue_depth: Gauge
    dropped_stale: Counter
    errors: Counter
    backpressure: Counter
    barge_in: Counter
    ttfa: Histogram
    ttfa_content: Histogram
    ws_frames: Counter
    ws_rejects: Counter


def build_stage_metrics(registry: CollectorRegistry) -> StageMetrics:
    """Register the foundation metrics on ``registry``.

    The app owns the registry. The process-global default registry is unused so
    two apps in one interpreter, and tests, do not collide.
    """
    return StageMetrics(
        latency=Histogram(
            "turnwise_stage_latency_seconds",
            "Handler time for one event that passed the staleness check.",
            labelnames=("stage",),
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        queue_depth=Gauge(
            "turnwise_queue_depth",
            "Events waiting in a stage inbox.",
            labelnames=("stage",),
            registry=registry,
        ),
        dropped_stale=Counter(
            "turnwise_events_dropped_stale",
            "Events dropped because their generation did not match the session.",
            labelnames=("stage",),
            registry=registry,
        ),
        errors=Counter(
            "turnwise_stage_errors",
            "Stage failures and misrouted events.",
            labelnames=("stage", "reason"),
            registry=registry,
        ),
        backpressure=Counter(
            "turnwise_backpressure_timeouts",
            "Inbox puts that exceeded the stage put timeout.",
            labelnames=("stage",),
            registry=registry,
        ),
        barge_in=Counter(
            "turnwise_barge_in",
            "Barge-in calls that bumped the session generation.",
            registry=registry,
        ),
        ttfa=Histogram(
            "turnwise_ttfa_seconds",
            "End of user speech to the first played audio frame, filler included.",
            buckets=_TTFA_BUCKETS,
            registry=registry,
        ),
        ttfa_content=Histogram(
            "turnwise_ttfa_content_seconds",
            "End of user speech to the first played non-filler audio frame.",
            buckets=_TTFA_BUCKETS,
            registry=registry,
        ),
        ws_frames=Counter(
            "turnwise_ws_frames",
            "WebSocket protocol messages accepted.",
            labelnames=("direction",),
            registry=registry,
        ),
        ws_rejects=Counter(
            "turnwise_ws_rejects",
            "WebSocket protocol messages rejected.",
            labelnames=("reason",),
            registry=registry,
        ),
    )
