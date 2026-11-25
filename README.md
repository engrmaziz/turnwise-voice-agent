# Turnwise

A fully local, streaming voice agent where deterministic dialogue control owns correctness, small speech and NLU models own the hot path, and an LLM handles only the long tail. Sub-800 ms time-to-first-audio on consumer hardware, with an automated spoken eval harness.

Clinic receptionist: book, reschedule, and cancel appointments, answer FAQs, escalate urgent symptoms, hand off to a human. $0 to run after the hardware you already own. No hosted speech or model API on the default path.

**This checkout is Phase 0 plus the event-bus skeleton (M1.1, M1.2).** There is no microphone path, recognizer, dialogue machine, or TTS yet. `GET /health` and `GET /metrics` work. Product SLOs are TARGETS and unmet.

## Scope

### Intents

`book`, `reschedule`, `cancel`, `check_appointment`, `faq`, `speak_to_human`, `urgent_symptom`, `out_of_scope`.

### Slots

`patient_name`, `dob`, `phone`, `doctor`, `date`, `time`, `reason`, `appointment_id`.

Closed-set entities (doctors) resolve against a catalog. Raw ASR text is never written to the database. Relative dates resolve from the session clock and timezone, not from a language model.

### Safety (deterministic)

Urgent-symptom keywords (chest pain, cannot breathe, and the list in settings) escalate even when every model is down or disagrees. The keyword path alone is sufficient. A classifier cannot veto it.

### Non-goals

HIPAA certification or a compliance claim. Server-side acoustic echo cancellation (browser `echoCancellation` only). Multilingual recognition, outbound dialing, payments, insurance eligibility, prescribing. Letting the language model choose dialogue state, check availability, write a booking, or decide urgency.

## SLO targets (unmet)

Definitions and formulas: [`docs/SLOs.md`](docs/SLOs.md). No product number below has been measured on a call. The only measured latency in this repo is an in-process stage hop (see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)).

| Metric | Target |
|---|---|
| Time-to-first-audio P50 / P95 | ≤ 700 ms / ≤ 1200 ms |
| Task success, clean audio | ≥ 90% |
| Task success, 10 dB SNR | ≥ 75% |
| False barge-in | < 2% of agent utterances |
| Early cutoff | < 5% of user turns |
| Slot F1 on ASR output | Report only until the golden set exists |
| Urgent-case recall | ~100% (keyword path sufficient) |
| Critical-slot error after confirmation | ~0% (confirmed value vs scenario truth) |
| FAQ hallucination rate | TARGET 0 on the FAQ set once the judge exists |

Time-to-first-content-audio and false urgent-escalation rate are recorded without a numeric cap.

## Architecture

Event-driven pipeline: one asyncio task per stage per call, bounded queues, every event stamped with `(session_id, turn_id, generation)`. Barge-in increments generation and turn, then cancels speaking tasks. Stale events drop. The dialogue FSM is the only writer of state. Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Decisions: [`docs/adr/`](docs/adr/). Execution plan: [`docs/plan/00_front_matter.md`](docs/plan/00_front_matter.md).

## Run

Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest
uv run python -m server
```

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
| M1.4 hardware benchmarks | not started |
| Phases 2–10 | not started |

Roadmap with acceptance lines: [`docs/ROADMAP.md`](docs/ROADMAP.md).
