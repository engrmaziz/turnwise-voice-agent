# Roadmap

The foundation in this repo is the prerequisite: the event bus, cancellation, settings, and telemetry described in `docs/ARCHITECTURE.md`. Phases below are the product. A phase is done when its acceptance checks pass, not when a module exists.

Ship a narrow call by the end of phase 4: silence endpointing, a deterministic slot matcher, templates, and one book path, with ten scripted checks against the database. Then replace those pieces one at a time. The deterministic matcher is not the long-term NLU. It leaves the default path when phase 5 lands. It does not parse model prose; structured model output stays grammar-constrained (ADR-001).

## Phase 1 — Transport and benchmarks

- WebSocket audio is PCM16, 16 kHz, 20 ms frames, and a tone round-trips.
- The browser client requests `echoCancellation`.
- `docs/benchmarks.md` records ASR real-time factor, language-model time-to-first-token and tokens per second, and TTS time-to-first-chunk on the named hardware.
- Audio events carry `frame_index` and generation. The foundation tests still pass.
- `/health` and `/metrics` still scrape.

## Phase 2 — Audio front end

- Ingress resamples to 16 kHz mono PCM16 once.
- Silero runs with hysteresis. Speech-start duration comes from settings.
- The recognizer receives about 500 ms of audio from before speech onset.
- Synthetic silence and clipping move the audio-quality metrics.
- The README states that server-side AEC is absent.

## Phase 3 — Streaming ASR and spoken form

- The recognizer emits partials and finals.
- Hotwords follow the dialogue state. An entity word-error ablation, biasing on and off, is written down.
- Inverse text normalization runs on finals only. Spoken form and normalized form are both kept.
- "Next Tuesday" is resolved with the session clock, including a DST boundary, in a unit test.
- A low-confidence critical slot asks for explicit confirmation.

## Phase 4 — Turns and barge-in

- Endpointing applies the expected-slot pause before the completion probability, so phone numbers and dates of birth are not cut at 200 ms.
- The turn classifier's CPU time is measured and fits a 10 ms budget on the bench machine, or the budget is revised in an ADR with the number.
- Backchannels are state-dependent. "Okay" during a yes/no question is a turn.
- Barge-in requires sustained speech plus a non-backchannel partial, and it records the audio the client acked, not the text the planner generated.
- Early-cutoff rate, response gap, false barge-in, and missed barge-in are emitted.
- The week-6 slice is in: silence endpointing, deterministic slots, templates, SQLite book, ten scripted database checks.

## Phase 5 — NLU

- Training text is TTS, then noise, then this recognizer. Clean transcripts are not the training distribution.
- A 500-example golden set is hand-checked.
- A table compares the teacher model and the student encoder on accuracy, slot F1, latency, and memory. Slot F1 is on recognizer output.
- A self-repair keeps the later slot value ("Tuesday — no, Wednesday").
- A test shows a closed-set entity cannot reach the database as raw ASR text.
- Phonetic thresholds are chosen from a sweep on the golden set, and the sweep is in the docs.
- The phase 4 deterministic matcher is off the default path.

## Phase 6 — Dialogue manager

- Transitions are a table. A Mermaid diagram is generated from that table.
- Model output that changes state, does date math, checks availability, writes a booking, or decides urgency fails a test.
- Proposals that do not validate leave the state unchanged.
- Two failed attempts on a slot change the ask ("spell that", "one digit at a time"). Three failures hand off with a summary.

## Phase 7 — Tools

- SQLite bookings use `BEGIN IMMEDIATE` and an idempotency key of `session_id` + `turn_id`. A retried write does not double-book.
- A slot taken between offer and confirm produces a new offer.
- A tool past 300 ms plays a cached filler. Time-to-first-audio and time-to-first-content-audio are both recorded.

## Phase 8 — Speech out

- The chunker flushes the first clause early and does not split "Dr." or "p.m.".
- Normalization speaks "Doctor", digit-by-digit phone numbers, and clock times. It is deterministic.
- Cached phrases show no model time in the TTS span.
- Client playback acks are what barge-in treats as heard.

## Phase 9 — Frustration and urgency

- The urgent keyword path escalates with the classifier disabled, in a test.
- False urgent escalation is reported on the non-urgent set.
- If the audio classifier times out, the score uses repair count, repeated "no", and barge-in only.
- Two turns over the threshold offer a human, shorten replies, and slow TTS.
- A calibration curve is in the docs, with the limitation that acted-emotion corpora transfer poorly to calls.

## Phase 10 — Evaluation

- Scenarios are YAML. Functional runs use a virtual clock. A smaller real-time set measures barge-in and time-to-first-audio.
- Task success is a database assertion.
- The judge model scores politeness and clarity only.
- A scripted, non-model caller subset is the CI gate.
- Ablations are published: silence-only versus semantic endpointing, biasing on versus off, NLU trained on clean text versus recognizer text, model-in-the-loop versus FSM-first, and the two ASR stacks.
- Nine hundred real-time calls are not described as an overnight run.

## Phase 11 — Hardening

- One trace per turn spans VAD, ASR final, turn end, NLU, dialogue, model time-to-first-token, TTS first chunk, and first audio out.
- The Grafana dashboard shows live histograms, queue depth, barge-in, and task outcomes.
- A load test reports the largest concurrency whose P95 time-to-first-audio still meets `docs/SLOs.md`, and the hardware it was run on.
- Language-model and TTS contention is measured for CPU TTS, a priority queue, and a capped model batch.
- Drills: model down still books via templates; TTS down still plays the cached set; an ASR confidence collapse offers a handoff.
- Names, dates of birth, and phone numbers are hashed in exported traces. Audio retention defaults off.
- The README describes HIPAA-style obligations and does not claim compliance.

## Phase 12 — Packaging

- `docker compose up` starts the server, the workers that were actually built, Grafana, and Jaeger, after a documented model download.
- The README shows the architecture, the SLO table with measured values beside the targets, the ablations, and the known limitations.
- ADR-003 is Accepted or still Proposed, matching whether a stack was chosen.
- A demo script covers a booking, a barge-in mid-confirmation, a noisy name resolved against the catalog, an urgent escalation, and the live dashboard.
