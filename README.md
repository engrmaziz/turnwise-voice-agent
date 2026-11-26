# Turnwise

A fully local, streaming voice agent where deterministic dialogue control owns correctness, small speech and NLU models own the hot path, and an LLM handles only the long tail. Sub-800 ms time-to-first-audio on consumer hardware, with an automated spoken eval harness.

Clinic receptionist: book, reschedule, and cancel appointments, answer FAQs, escalate urgent symptoms, hand off to a human. $0 to run after the hardware you already own. No hosted speech or model API on the default path.

**This checkout is Phase 0 through Phase 10.** The event bus, PCM16 WebSocket, Silero VAD, a stub streaming ASR, rule-based ITN, clinic-clock date resolution, a hybrid endpointer, gated barge-in, spoken NLU, the table-driven dialogue FSM, token-overlap FAQ, SQLite bookings, streaming TTS (silence stub + phrase cache), play-ack TTFA, paralinguistic courtesy (fusion + two-turn offer), a scripted eval harness (DB judge, virtual-clock matrix, CI smoke), per-turn traces, Grafana panels 1–12, a scripted load driver, three degradation drills, model lock/download, and compose packaging are in. The LLM client is a stub. Real ASR, TTS, and emotion weights are not pinned (ADR-006, ADR-010, ADR-011 blocked). The golden NLU set is `golden_incomplete`; slot F1 is unpublished. Product SLOs are TARGETS and unmet. Acted-emotion F1 is not a product number. Nine hundred virtual calls are not claimed. Load knee is `n=0 failed at 1` because the scripted caller does not play-ack. ADR-003 stays Proposed. ADR-004 and ADR-013 stay blocked.

## Scope

### Intents

`book`, `reschedule`, `cancel`, `check_appointment`, `faq`, `speak_to_human`, `urgent_symptom`, `out_of_scope`.

### Slots

`patient_name`, `dob`, `phone`, `doctor`, `date`, `time`, `reason`, `appointment_id`.

Closed-set entities (doctors) resolve against a catalog. Raw ASR text is never written to the database. Relative dates resolve from the session clock and timezone, not from a language model.

### Safety (deterministic)

Urgent-symptom keywords (chest pain, cannot breathe, and the list in settings) escalate even when every model is down or disagrees. The keyword path alone is sufficient. A classifier cannot veto it. Audio emotion is courtesy only (`emotion_model_enabled` false; ADR-011). Two over-threshold turns offer a human; that offer is not a handoff.

### Non-goals

HIPAA certification or a compliance claim. Server-side acoustic echo cancellation (browser `echoCancellation` only). Multilingual recognition, outbound dialing, payments, insurance eligibility, prescribing. Letting the language model choose dialogue state, check availability, write a booking, or decide urgency. ADR-003 stays Proposed: no ASR/LLM/TTS stack is named from measured `ok` cells.

## SLO targets (unmet)

Definitions and formulas: [`docs/SLOs.md`](docs/SLOs.md). No product TTFA has been measured on a call. Virtual-clock task success is not an SLO quote (ADR-012). Every millisecond or percent in the table cites a `docs/results/` file.

| Metric | Target and measured |
|---|---|
| Time-to-first-audio P50 / P95 | TARGET ≤ 700 ms / ≤ 1200 ms, unmet. Realtime subset skipped (`docs/results/phase9.md`). Load knee `n=0 failed at 1`, no play-ack p95 (`docs/results/phase10_load.md`). |
| Task success, clean audio | TARGET ≥ 90%. Smoke `task_success` 0.9 is virtual-clock, not this SLO (`docs/results/phase9.md`). |
| Task success, 10 dB SNR | TARGET ≥ 75%. Matrix `task_success` 0.888… is virtual-clock n=9, not this SLO (`docs/results/phase9.md`). |
| False barge-in | TARGET < 2% of agent utterances. Realtime subset skipped (`docs/results/phase9.md`). |
| Early cutoff | TARGET < 5% of user turns. Realtime subset skipped (`docs/results/phase9.md`). |
| Slot F1 on ASR output | Report only (`golden_incomplete`; unpublished) (`docs/results/phase5.md`). |
| Urgent-case recall | TARGET ~100% (keyword path sufficient). Keyword drill in (`docs/results/phase9.md`). |
| Critical-slot error after confirmation | TARGET ~0% (confirmed value vs scenario truth) (`docs/results/phase9.md`). |
| FAQ hallucination rate | TARGET 0 on the FAQ set (`docs/results/phase9.md`). |

Time-to-first-content-audio and false urgent-escalation rate are recorded without a numeric cap.

## Privacy (not a compliance claim)

Configured PII keys (names, dates of birth, phones) are HMAC-hashed in logs. Spans carry `session_id`, `turn_id`, `generation`, `stage`, `model`, and `latency_ms`; they must not carry payload names. Audio retention defaults off (`TURNWISE_AUDIO_RETAIN=false`). Compose does not flip that flag on. This paragraph describes engineering controls. It is not HIPAA certification, a BAA, or permission to run Turnwise as a covered-entity production system.

## Architecture

Event-driven pipeline: one asyncio task per stage per call, bounded queues, every event stamped with `(session_id, turn_id, generation)`. Barge-in increments generation and turn, then cancels speaking tasks. Stale events drop. The dialogue FSM is the only writer of state. Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Decisions: [`docs/adr/`](docs/adr/). Execution plan: [`docs/plan/00_front_matter.md`](docs/plan/00_front_matter.md).

## Run

Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run python scripts/download_silero_vad.py
uv run pytest
uv run python -m evals.bench
uv run python scripts/download_models.py
uv run python -m evals.smoke_gate --write-only
uv run python -m evals.load --n 2 --out-dir docs/results
uv run python -m server
```

Silero weights are gitignored. Without the download script the process uses the energy-gate fallback and increments `turnwise_vad_fallback`.

- `GET http://127.0.0.1:8000/` — capture client (needs a microphone; wear headphones)
- `WS  http://127.0.0.1:8000/v1/audio` — binary PCM16 frames
- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/metrics`

Observability stack (app, Prometheus, Grafana, Jaeger):

```bash
docker compose -f infra/docker-compose.yml up --build
```

Settings: [`.env.example`](.env.example), `TURNWISE_` prefix. An unset `TURNWISE_PII_HASH_KEY` generates a process-local HMAC key and logs `pii_hash_key_unset` once.

## Status

| Milestone | State |
|---|---|
| Phase 0 scope (this README, SLOs, ADRs) | done |
| M1.1 tooling, config, CI, telemetry | done |
| M1.2 event bus, session, bounded stages | done |
| M1.3 WebSocket PCM16 + browser client | done (headphone check not run; see `docs/results/phase1.md`) |
| M1.4 hardware benchmarks | done (model rows blocked until weights exist; see `docs/benchmarks.md`) |
| M2.1 resample once + frame clock | done |
| M2.2 AEC flag gates barge-in | done (speaker row not run; see `docs/results/phase2.md`) |
| M2.3 Silero VAD, hysteresis, pre-roll | done |
| M2.4 silence / clip quality | done |
| M3.1 stub ASR pool, partials and finals | done |
| M3.2 Zipformer vs Whisper+LA-2 | done (both backends blocked; see ADR-006) |
| M3.3 hotwords + entity WER | done (entity WER blocked; TTS missing) |
| M3.4 ITN, spoken form kept | done (NeMo missing; rule fallback) |
| M3.5 relative dates + slot confidence | done |
| M4.1 hybrid endpointer, digit patience | done |
| M4.2 turn-completeness classifier | done (see `docs/results/phase4.md`) |
| M4.3 barge-in, backchannels, playback prefix | done |
| M4.4 cancel latency + turn counters | done |
| M5.1 synthetic caller corpus | done (200 hand_authored; LLM blocked) |
| M5.2 render, recognize, align, teach | done (stub ASR; teacher blocked) |
| M5.3 golden set | done (`golden_incomplete`; 20-row CI fixture only) |
| M5.4 joint student + NLU stage | done (see `docs/results/phase5.md`; slot F1 unpublished) |
| M5.5 disfluency + phonetic resolve | done (sweep `untuned`) |
| M6.1 table-driven FSM + validators | done (see `docs/results/phase6.md`) |
| M6.2 confirm policy + repair ladder | done |
| M6.3 LLM stub, proposals, FAQ overlap | done (LLM binary blocked; ADR-009) |
| M6.4 SQLite calendar + idempotency | done |
| M6.5 tool timeouts + filler | done (filler_delta_ms 306.969) |
| M6.6 urgent keywords | done (NLU cannot veto) |
| M7.1 templates + paraphrase slots | done |
| M7.2 abbreviation-safe chunker | done |
| M7.3 deterministic TN | done |
| M7.4 phrase cache, play frames, TTFA | done (stub TTS; ADR-010 CPU; see [`docs/results/phase7.md`](docs/results/phase7.md)) |
| M8.1 utterance emotion stub | done (acted train skipped; timeout → `None`; see [`docs/results/phase8.md`](docs/results/phase8.md)) |
| M8.2 late fusion + lexicon | done (no-audio path 0.4 / 0.6; weights sum 1.0) |
| M8.3 two-turn offer, not handoff | done (keywords still win) |
| M8.4 calibration / default-off | done (`not_collected`; ADR-011) |
| M9.1 scenario schema + scripted caller | done (see [`docs/results/phase9.md`](docs/results/phase9.md)) |
| M9.2 spoken caller / render / barge inject | done (LLM caller blocked; T1.4.3) |
| M9.3 DB judge; soft cannot override | done |
| M9.4 virtual matrix + realtime skip | done (actual n in JSON; ADR-012) |
| M9.5 ablations + CI smoke | done (result-or-blocked; unsafe writer not in `server/`) |
| M10.1 per-turn traces + Grafana 8–12 | done (GPU skip panel; see `infra/grafana/dashboards/turnwise.json`) |
| M10.2 load knee + LLM priority/batch | done (knee `n=0 failed at 1`; ADR-013 blocked; [`docs/results/phase10_load.md`](docs/results/phase10_load.md)) |
| M10.3 degrade drills, span PII, retain off | done |
| M10.4 lock/download, compose, missing weights | done ([`docs/results/phase10_compose.md`](docs/results/phase10_compose.md), [`docs/RUN.md`](docs/RUN.md)) |
| M10.5 README sources, demo, blog, ADR index | done ([`docs/demo.md`](docs/demo.md), [`docs/blog/generation_cancellation.md`](docs/blog/generation_cancellation.md)) |
| Phase 10 | done |

Roadmap with acceptance lines: [`docs/ROADMAP.md`](docs/ROADMAP.md).
