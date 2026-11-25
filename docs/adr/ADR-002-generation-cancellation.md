# ADR-002: Bounded queues and generation-based cancellation

- Status: Accepted
- Date: 2026-11-25

## Context

A full-duplex call has to stop speaking when the caller interrupts, and it has to do that without each stage knowing the others. Unbounded queues hide the moment a stage falls behind: latency grows until the call is unusable. Cancelling an asyncio task does not cancel an in-flight GPU call that was submitted earlier.

## Decision

Each session owns one asyncio task per stage. Stages connect only through bounded `asyncio.Queue`s. Queue size and put timeout come from settings (`stage_queue_maxsize` default 32, `stage_put_timeout_s` default 0.25 seconds).

A put that is still waiting when the timeout elapses raises `StageBackpressureError`, increments `turnwise_backpressure_timeouts_total`, and fails the producing stage. The inbox does not drop the oldest event to make room. Backpressure is the signal.

Every event is immutable and carries `session_id`, `turn_id`, `generation`, and an optional `frame_index`. Producers stamp `generation` from the session at creation time.

`Session.barge_in` increments `generation` and `turn_id`, then cancels tasks registered with `track_speaking`. It does not await between the increment and the cancels. The turn increment keeps the interrupted utterance and the new caller speech in different traces. `next_turn` advances the turn without cancelling speech, for a clean handoff to the next caller utterance.

Consumers drop an event when `event.generation != session.generation` or the event belongs to another session id. Stale drops are expected during barge-in. They increment `turnwise_events_dropped_stale_total` and do not fail the stage. A foreign or missing session is counted on `turnwise_stage_errors_total` and dropped; the stage stays up so one misrouted event does not end the call. A rising foreign-session count is a routing bug.

Stage tasks catch `CancelledError`, run their cleanup hook once, and re-raise. On Python 3.11+ the task is uncancelled first, because a task that is still marked cancelling raises `CancelledError` at the next await and would skip cleanup.

Worker pools, when they exist, must capture `generation` at submit time and discard the result when the session generation has moved. `task.cancel()` does not abort an in-flight ONNX or llama.cpp call. Pools are not part of this milestone.

`frame_index` is the shared audio clock for ingress, VAD, ASR, and playback acks. Playback grounding uses client acks, not the server send cursor, because the jitter buffer runs ahead of the speaker. Nothing records playback yet.

## Consequences

- Model workers are shared across sessions (ADR-003) but each result is tagged with the submitting generation.
- Batch waits inside those pools have to stay at a few milliseconds. Filling a batch fights the time-to-first-audio target.
- The session that is being talked over gets priority on the ASR pool once that pool exists, so barge-in is not queued behind another call.
- `session_id` is an opaque id. It is logged and spanned in the clear. Names, dates of birth, and phone numbers stay in the payload, which logging omits and spans do not copy.
