# Three-minute demo

Wear headphones. `TURNWISE_AUDIO_RETAIN` stays false. Open `http://127.0.0.1:8000/` after `uv run python -m server` or compose. Default TTS is silence. To hear Piper: `uv sync --extra tts`, `python scripts/download_models.py`, `TURNWISE_TTS_BACKEND=piper`.

Each beat has a spoken caller line and an on-screen check. Stub ASR may not match the spoken words; the check is still what a human looks at.

## Beat 1 — happy-path book (0:00–0:40)

**Caller:** "Hi, this is Avery Chen, date of birth March third nineteen ninety, phone five five five zero one zero zero one two three. I want to book with Doctor Patel next Tuesday at two thirty for a checkup."

**Check:** The client stays connected. After confirm, `/metrics` can show `turnwise_task_outcome_total{state="CLOSE"}` increment on a real FSM close. Scripted equivalent: `evals/scenarios/smoke/book_avery.yaml` writes one SQLite row.

## Beat 2 — barge-in mid-confirm (0:40–1:10)

**Caller:** Interrupt the confirm readback with "wait, Wednesday instead."

**Check:** Playback stops. A new generation starts. Grafana panel 5 (`turnwise_barge_in_total`) moves if the barge policy fired. Scripted equivalent: `evals/scenarios/examples/barge_mid_confirm.yaml`.

## Beat 3 — noisy name (1:10–1:40)

**Caller:** "It's Doctor Khan" (or a muffled roster name).

**Check:** The roster resolves to a catalog id. Raw ASR text is not the doctor column in SQLite. Scripted equivalent: `evals/scenarios/examples/noisy_name.yaml`.

## Beat 4 — urgent keyword (1:40–2:20)

**Caller:** "I have chest pain."

**Check:** The agent speaks the emergency template and the FSM is `URGENT`. Keywords win even with the emotion model off. Grafana panel 8 can show `state="URGENT"`. Scripted equivalent: `evals/scenarios/examples/urgent_breathe.yaml`.

## Beat 5 — Grafana (2:20–3:00)

**Caller:** (none) Open Grafana at `http://127.0.0.1:3000` (anonymous viewer) dashboard `Turnwise`.

**Check:** Panels 1–12 exist. TTFA panels 6–7 stay empty until a play-ack. Panel 13 is the GPU skip (`vector(0)`; no `nvidia-smi` on the event loop). Jaeger at `http://127.0.0.1:16686` shows a parent span `turn` after a `TURN_END`; missing children are `stage.skipped` events, not invented spans.
