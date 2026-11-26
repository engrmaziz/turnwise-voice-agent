"""HTTP surface for this milestone: liveness and Prometheus scrape."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from pydantic import BaseModel

from dialogue.templates import load_templates
from models.asr_pool import AsrPool
from models.llm_client import LlmClient
from models.nlu_pool import NluScorer
from models.onnx_pool import TurnScorer
from models.tts_cache import TtsCache, warmup_cache, warmup_texts
from models.tts_pool import TtsPool, load_tts_pool
from models.vad_pool import VadEngine, VadPool
from pipeline.metrics import StageMetrics, build_stage_metrics
from pipeline.session import SessionStore
from pipeline.stages.audio_in import AudioInHandler
from server.config import Settings, get_settings
from server.log_setup import configure_logging
from server.pii import PiiRedactor
from server.playback import ClosedCallSnapshot
from server.telemetry import Tracing, start_tracing


def new_audio_handler() -> AudioInHandler:
    return AudioInHandler()


def unavailable_vad() -> VadEngine:
    return VadPool.unavailable(timeout_ms=30)


class HealthResponse(BaseModel):
    status: str
    service: str


@dataclass(slots=True)
class AppContainer:
    """Process-owned dependencies. One container per ASGI app, injected into routes."""

    settings: Settings
    registry: CollectorRegistry
    metrics: StageMetrics
    sessions: SessionStore
    redactor: PiiRedactor
    tracing: Tracing | None = None
    closed_snapshots: list[ClosedCallSnapshot] | None = None
    make_audio_handler: Callable[[], AudioInHandler] = field(default=new_audio_handler)
    vad_engine: VadEngine = field(default_factory=unavailable_vad)
    asr_pool: AsrPool | None = None
    turn_scorer: TurnScorer | None = None
    nlu_scorer: NluScorer | None = None
    llm_client: LlmClient | None = None
    tts_pool: TtsPool | None = None
    tts_cache: TtsCache | None = None


class TurnwiseApp(FastAPI):
    """FastAPI app that carries a typed container instead of ``app.state``."""

    def __init__(
        self,
        container: AppContainer,
        lifespan: object,
    ) -> None:
        # Lifespan is a Starlette callable. The precise type is a contextmanager
        # factory; object keeps this constructor from depending on Starlette internals.
        super().__init__(title="Turnwise", lifespan=lifespan)  # type: ignore[arg-type]
        self.container = container


def create_app(settings: Settings | None = None) -> TurnwiseApp:
    """Build the ASGI app. Tracing starts in the lifespan, not at import."""
    resolved = settings if settings is not None else get_settings()
    registry = CollectorRegistry()
    metrics = build_stage_metrics(registry)
    vad_engine = _load_vad(resolved)
    asr_pool = _load_asr(resolved, metrics)
    turn_scorer = _load_turn(resolved)
    nlu_scorer = _load_nlu(resolved)
    llm_client = LlmClient.unavailable(timeout_ms=resolved.llm_timeout_ms)
    load_templates()
    tts_pool = load_tts_pool(resolved)
    phrases = warmup_texts(resolved)
    tts_cache = TtsCache(
        warmup_ids=frozenset(resolved.tts_warmup_list),
        warmup_texts=frozenset(phrases.values()),
    )
    warmup_cache(tts_cache, tts_pool, resolved, metrics)
    container = AppContainer(
        settings=resolved,
        registry=registry,
        metrics=metrics,
        sessions=SessionStore(
            on_barge_in=lambda: metrics.barge_in.inc(),
            timezone=ZoneInfo(resolved.clinic_timezone),
        ),
        redactor=PiiRedactor(resolved),
        closed_snapshots=[],
        vad_engine=vad_engine,
        asr_pool=asr_pool,
        turn_scorer=turn_scorer,
        nlu_scorer=nlu_scorer,
        llm_client=llm_client,
        tts_pool=tts_pool,
        tts_cache=tts_cache,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        configure_logging(container.settings, container.redactor)
        container.tracing = start_tracing(container.settings)
        try:
            yield
        finally:
            tracing = container.tracing
            container.tracing = None
            if tracing is not None:
                tracing.shutdown()
            engine = container.vad_engine
            if engine is not None:
                engine.close()
            pool = container.asr_pool
            if pool is not None:
                pool.close()
            scorer = container.turn_scorer
            if scorer is not None:
                scorer.close()
            nlu = container.nlu_scorer
            if nlu is not None:
                nlu.close()
            tts = container.tts_pool
            if tts is not None:
                tts.close()

    app = TurnwiseApp(container=container, lifespan=lifespan)
    client_dir = Path(__file__).resolve().parent.parent / "client"

    @app.websocket(resolved.ws_path)
    async def audio_socket(websocket: WebSocket) -> None:
        from server.ws import handle_audio_socket

        await handle_audio_socket(websocket, app.container)

    @app.get("/")
    async def ui() -> FileResponse:
        return FileResponse(client_dir / "index.html")

    @app.get("/main.js")
    async def ui_js() -> FileResponse:
        return FileResponse(client_dir / "main.js", media_type="text/javascript")

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        current = _container(request)
        return HealthResponse(status="ok", service=current.settings.service_name)

    @app.get("/metrics")
    async def metrics_route(request: Request) -> Response:
        current = _container(request)
        if not current.settings.metrics_enabled:
            return Response(status_code=404)
        payload = generate_latest(current.registry)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

    return app


def _load_asr(settings: Settings, metrics: StageMetrics) -> AsrPool:
    backend = settings.asr_backend.strip()
    if backend in {"", "stub"}:
        return AsrPool.stub(settings, metrics)
    return AsrPool.load_real(settings, metrics)


def _load_turn(settings: Settings) -> TurnScorer:
    path = Path(settings.turn_onnx_path)
    if not path.is_file():
        return TurnScorer.unavailable(timeout_ms=settings.turn_timeout_ms)
    return TurnScorer.load(
        path,
        timeout_ms=settings.turn_timeout_ms,
        feature_dim=settings.turn_feature_dim,
        ngram=settings.turn_ngram,
    )


def _load_nlu(settings: Settings) -> NluScorer:
    path = Path(settings.nlu_model_path.strip())
    if not settings.nlu_model_path.strip() or not path.is_file():
        return NluScorer.unavailable(timeout_ms=settings.nlu_timeout_ms)
    bio = path.with_name("nlu_bio.onnx")
    if not bio.is_file():
        return NluScorer.unavailable(timeout_ms=settings.nlu_timeout_ms)
    return NluScorer.load(
        path,
        bio,
        timeout_ms=settings.nlu_timeout_ms,
        feature_dim=settings.nlu_feature_dim,
        ngram=settings.nlu_ngram,
    )


def _load_vad(settings: Settings) -> VadEngine:
    path = Path(settings.vad_onnx_path)
    if not path.is_file():
        return VadPool.unavailable(timeout_ms=settings.vad_timeout_ms)
    return VadPool.load(
        path,
        timeout_ms=settings.vad_timeout_ms,
        window_samples=settings.vad_window_samples,
        sample_rate_hz=settings.ws_sample_rate_hz,
    )


def _container(request: Request) -> AppContainer:
    app = request.app
    if not isinstance(app, TurnwiseApp):
        raise RuntimeError("Turnwise routes mounted on an unexpected ASGI app")
    return app.container
