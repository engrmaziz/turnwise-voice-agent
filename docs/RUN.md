# Run Turnwise

Python 3.11+, [uv](https://docs.astral.sh/uv/), optional Docker for the observability stack.

## Local process

```bash
uv sync --all-groups
uv run python scripts/download_silero_vad.py
uv run python scripts/download_models.py
uv run pytest
uv run python -m server
```

`scripts/download_models.py` reads `models/lock.toml`. A sha256 mismatch exits 1. Empty hashes skip unless you pass `--required`. Default `--required` is false so CI stays weight-free.

`GET http://127.0.0.1:8000/health` is 200 even when ASR/TTS/LLM weights are missing. The JSON then has `degraded_asr`, `degraded_tts`, and `degraded_llm` true.

`TURNWISE_AUDIO_RETAIN` defaults false. Do not flip it on for a demo recording and leave it on. Compose must not set it to true.

## Compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

That starts the app (`:8000`), Prometheus (`:9090`), Grafana (`:3000`, anonymous viewer), and Jaeger (UI `:16686`). Jaeger OTLP gRPC stays on the compose network at `jaeger:4317` and is not published on the host, so a local collector already bound to 4317 does not block the container. Prometheus still needs host 9090.

Recorded boot: [`docs/results/phase10_compose.md`](results/phase10_compose.md). A fail in that file is a fail.

## Load

```bash
uv run python -m evals.load --n 2 --out-dir docs/results
```

The driver stops after two consecutive P95 misses versus 1200 ms. Scripted callers do not play-ack, so N=1 is already a miss and the knee is `n=0 failed at 1`. JSON includes `platform.platform()` and `adr004_tier=blocked`.
