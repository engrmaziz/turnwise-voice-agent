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
    resample: Histogram
    clock_gaps: Counter
    aec_disabled: Counter
    vad_prob: Histogram
    vad_latency: Histogram
    vad_fallback: Counter
    vad_hang: Counter
    preroll_underrun: Counter
    audio_dead: Counter
    audio_clipped: Counter
    asr_finalize: Histogram
    asr_dropped_generation: Counter
    asr_stable_lag: Histogram
    hotword_updates: Counter
    itn_errors: Counter
    itn_seconds: Histogram
    temporal_unresolved: Counter
    temporal_seconds: Histogram
    endpoint_decisions: Counter
    endpoint_silence: Histogram
    turn_model_seconds: Histogram
    turn_model_timeouts: Counter
    backchannel_ignored: Counter
    playback_unmap: Counter
    playback_ack_ahead: Counter
    cancel_latency: Histogram
    response_gap: Histogram
    early_cutoff: Counter
    false_barge_in: Counter
    missed_barge_in: Counter
    nlu_seconds: Histogram
    nlu_reject: Counter
    disambiguation: Counter
    repair_applied: Counter


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
        resample=Histogram(
            "turnwise_audio_resample_seconds",
            "Time to resample one ingress frame to 16 kHz mono PCM16.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        clock_gaps=Counter(
            "turnwise_audio_clock_gaps",
            "Client frame indexes that skipped one or two expected frames.",
            registry=registry,
        ),
        aec_disabled=Counter(
            "turnwise_aec_disabled_sessions",
            "Sessions whose hello reported echoCancellation false.",
            registry=registry,
        ),
        vad_prob=Histogram(
            "turnwise_vad_prob",
            "Silero (or energy-fallback) speech probability.",
            buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0),
            registry=registry,
        ),
        vad_latency=Histogram(
            "turnwise_vad_latency_seconds",
            "VAD inference time including executor wait.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        vad_fallback=Counter(
            "turnwise_vad_fallback",
            "Frames scored by the energy gate instead of ONNX.",
            registry=registry,
        ),
        vad_hang=Counter(
            "turnwise_vad_hang",
            "Utterances forced idle by vad_max_utterance_ms.",
            registry=registry,
        ),
        preroll_underrun=Counter(
            "turnwise_preroll_underrun",
            "Speech starts whose pre-roll was shorter than vad_preroll_ms.",
            registry=registry,
        ),
        audio_dead=Counter(
            "turnwise_audio_dead",
            "Sessions closed after a silent microphone window.",
            registry=registry,
        ),
        audio_clipped=Counter(
            "turnwise_audio_clipped",
            "Sessions flagged for clipping.",
            registry=registry,
        ),
        asr_finalize=Histogram(
            "turnwise_asr_finalize_seconds",
            "Time to finish one utterance decode including executor wait.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        asr_dropped_generation=Counter(
            "turnwise_asr_dropped_generation",
            "ASR hypotheses dropped because session generation moved.",
            registry=registry,
        ),
        asr_stable_lag=Histogram(
            "turnwise_asr_stable_lag_seconds",
            "Delay from audio event to a newly stable prefix.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        hotword_updates=Counter(
            "turnwise_hotword_updates",
            "Hotword list rebuilds after expected_vocab_id changed.",
            registry=registry,
        ),
        itn_errors=Counter(
            "turnwise_itn_errors",
            "ITN timeouts and exceptions that kept spoken form.",
            registry=registry,
        ),
        itn_seconds=Histogram(
            "turnwise_itn_seconds",
            "ITN wall time including executor wait.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        temporal_unresolved=Counter(
            "turnwise_temporal_unresolved",
            "Finals whose relative date produced no instant.",
            registry=registry,
        ),
        temporal_seconds=Histogram(
            "turnwise_temporal_seconds",
            "Relative-date resolver wall time.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        endpoint_decisions=Counter(
            "turnwise_endpoint_decisions",
            "Endpointer hold versus end decisions.",
            labelnames=("result",),
            registry=registry,
        ),
        endpoint_silence=Histogram(
            "turnwise_endpoint_silence_ms",
            "Silence at the moment of an endpointer decision, in milliseconds.",
            buckets=(50.0, 100.0, 200.0, 500.0, 800.0, 1000.0, 1200.0, 2000.0, 5000.0),
            registry=registry,
        ),
        turn_model_seconds=Histogram(
            "turnwise_turn_model_seconds",
            "Turn-completeness ONNX wall time including executor wait.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        turn_model_timeouts=Counter(
            "turnwise_turn_model_timeouts",
            "Turn-completeness inferences that exceeded turn_timeout_ms.",
            registry=registry,
        ),
        backchannel_ignored=Counter(
            "turnwise_backchannel_ignored",
            "Barge-in candidates dropped as state-dependent backchannels.",
            registry=registry,
        ),
        playback_unmap=Counter(
            "turnwise_playback_unmap",
            "Barge-in with no frame-to-text map; played_text is empty.",
            registry=registry,
        ),
        playback_ack_ahead=Counter(
            "turnwise_playback_ack_ahead",
            "Play acks whose frame index is ahead of any sent chunk.",
            registry=registry,
        ),
        cancel_latency=Histogram(
            "turnwise_cancel_latency_seconds",
            "Time from barge_in return to last outbound PCM write.",
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
            registry=registry,
        ),
        response_gap=Histogram(
            "turnwise_response_gap_seconds",
            "TURN_END to first server outbound PCM write. Not TTFA.",
            buckets=_TTFA_BUCKETS,
            registry=registry,
        ),
        early_cutoff=Counter(
            "turnwise_early_cutoff",
            "TURN_END labeled as firing before the scenario's last token.",
            registry=registry,
        ),
        false_barge_in=Counter(
            "turnwise_false_barge_in",
            "Cancels whose fixture label is not should_barge.",
            registry=registry,
        ),
        missed_barge_in=Counter(
            "turnwise_missed_barge_in",
            "Labeled should_barge bursts the policy did not cancel.",
            registry=registry,
        ),
        nlu_seconds=Histogram(
            "turnwise_nlu_seconds",
            "NLU student wall time including executor wait.",
            buckets=_STAGE_BUCKETS,
            registry=registry,
        ),
        nlu_reject=Counter(
            "turnwise_nlu_reject",
            "NLU timeouts and missing weights that emitted nlu_ok=0.",
            registry=registry,
        ),
        disambiguation=Counter(
            "turnwise_disambiguation",
            "Doctor spans that did not resolve to a single catalog id.",
            registry=registry,
        ),
        repair_applied=Counter(
            "turnwise_repair_applied",
            "Utterances where a self-repair replaced an earlier slot span.",
            registry=registry,
        ),
    )


def observe_response_gap(metrics: StageMetrics, turn_end_ts: float, first_audio_ts: float) -> None:
    """Record first outbound write minus TURN_END. Both clocks are monotonic."""
    metrics.response_gap.observe(max(0.0, first_audio_ts - turn_end_ts))
