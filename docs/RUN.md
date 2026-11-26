# Run Turnwise

Python 3.11+, [uv](https://docs.astral.sh/uv/), optional Docker for the observability stack.

## Local process

```bash
uv sync --all-groups --extra tts --extra asr
uv run python scripts/download_silero_vad.py
uv run python scripts/download_models.py
uv run pytest
uv run python -m server
```

`scripts/download_models.py` reads `models/lock.toml`. A sha256 mismatch exits 1. Empty hashes skip unless you pass `--required`. Default `--required` is false so CI stays weight-free. The Piper extra (`uv sync --extra tts`) and Zipformer extra (`uv sync --extra asr`) are optional; CI does not install them. After the voice files land, set `TURNWISE_TTS_BACKEND=piper` to leave the silence stub. After Zipformer weights land, set `TURNWISE_ASR_BACKEND=zipformer` to leave the stub recognizer. After a local Ollama model exists, set `TURNWISE_LLM_BACKEND=ollama`. Defaults stay empty.

`GET http://127.0.0.1:8000/health` is 200 even when ASR/TTS/LLM weights are missing. The JSON then has `degraded_asr`, `degraded_tts`, and `degraded_llm` true. `tts_backend=piper` with a missing ONNX is still 200 and `degraded_tts` true.

`TURNWISE_AUDIO_RETAIN` defaults false. Do not flip it on for a demo recording and leave it on. Compose must not set it to true.

## Compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

That starts the app (`:8000`), Prometheus (`:9090`), Grafana (`:3000`, anonymous viewer), and Jaeger (UI `:16686`). Jaeger OTLP gRPC stays on the compose network at `jaeger:4317` and is not published on the host, so a local collector already bound to 4317 does not block the container. If host 8000 or 9090 is already taken, override `TURNWISE_HOST_HTTP_PORT` and `TURNWISE_HOST_PROM_PORT` (and `TURNWISE_HOST_GRAFANA_PORT` if 3000 is busy).

Recorded boot: [`docs/results/phase10_compose.md`](results/phase10_compose.md). A fail in that file is a fail.

## Load

```bash
uv run python -m evals.load --n 2 --out-dir docs/results
uv run python -m evals.load --tts-backend piper --out-dir docs/results
```

The driver stamps a synthetic TURN_END, runs TTS, and acks play index 0. It stops after two consecutive misses (no play-ack on every session, or histogram p95 over 1200 ms). p95 is a histogram bucket bound. `product_quote=false`. Stub column: knee 16 (`docs/results/phase10_load.md`). Piper column: knee 1 (`docs/results/phase10_load_piper.md`). Neither is a product TTFA quote. JSON includes `platform.platform()` and `adr004_tier=blocked`.
