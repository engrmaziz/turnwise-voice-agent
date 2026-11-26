# Phase 10 compose boot

Operator: this machine. Compose file: `infra/docker-compose.yml`. Command: `docker compose -f infra/docker-compose.yml up --build`.

- `docker compose version`: Docker Compose version v5.5.1
- `TURNWISE_AUDIO_RETAIN` was not set true in compose.

## Result: fail

The app image built. The in-container health probe is 200 with degraded flags. The full stack did not start: Prometheus never bound, Grafana stayed `Created`.

## Attempts

| Attempt | Duration s | Exit | What happened |
|---|---|---|---|
| 1 | 23.095 | 1 | Image build failed: `.dockerignore` listed `client`, so `COPY client ./client` had no context. |
| 2 | 352.309 | 1 | Image built after dropping `client` from `.dockerignore`. Jaeger host port 4317: `Bind for 127.0.0.1:4317 failed: port is already allocated`. |
| 3 | 14.364 | 1 | Jaeger host 4317 unpublished (app still uses `http://jaeger:4317` on the compose network). App started `healthy`. Prometheus: `Bind for 127.0.0.1:9090 failed: port is already allocated`. Grafana never started. |

## In-container health (attempt 3)

```
STATUS 200
{"status":"ok","service":"turnwise","degraded_llm":true,"degraded_tts":true,"degraded_asr":true}
```

Host `curl http://127.0.0.1:8000/health` returned 404 (`{"detail":"Not Found"}`). Docker published `0.0.0.0:8000->8000`, so another process is likely already bound on the host. The number above is from `docker compose exec app` against `127.0.0.1:8000` inside the container.

A fail is a fail. This file does not treat `docker compose config` as a boot.
