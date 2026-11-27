# Phase 10 compose boot

Operator: this machine. Compose file: `infra/docker-compose.yml`. Command: `docker compose -f infra/docker-compose.yml up --build`.

- `docker compose version`: Docker Compose version v5.5.1
- `TURNWISE_AUDIO_RETAIN` was not set true in compose.
- Host publishes: HTTP `8010`, Prometheus `9080`, Jaeger OTLP `4217` (container still uses `8000` / `9090` / `4317`). Grafana host `3000` was already bound, so this boot used `TURNWISE_HOST_GRAFANA_PORT=3010`.

## Result: pass

Host probes against the remapped ports returned 200. In-container health is 200 with degraded flags (compose image does not ship Piper/Zipformer/Ollama).

## Host health

```
GET http://127.0.0.1:8010/health
STATUS 200
{"status":"ok","service":"turnwise","degraded_llm":true,"degraded_tts":true,"degraded_asr":true}
```

```
GET http://127.0.0.1:9080/-/healthy
STATUS 200
```

TCP connect to `127.0.0.1:4217` succeeded (Jaeger OTLP gRPC published as `4217:4317`).

## Services

| Service | Host bind | Status |
|---|---|---|
| app | `8010→8000` | healthy |
| prometheus | `9080→9090` | up |
| jaeger UI | `16686` | up |
| jaeger OTLP | `4217→4317` | listening |
| grafana | `3010→3000` (override; default 3000 was taken) | started after override |

A fail is a fail. This file is a host-curl boot, not `docker compose config`.
