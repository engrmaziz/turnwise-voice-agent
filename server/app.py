"""HTTP surface for this milestone: liveness and Prometheus scrape."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from pydantic import BaseModel

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
    container = AppContainer(
        settings=resolved,
        registry=registry,
        metrics=metrics,
        sessions=SessionStore(on_barge_in=lambda: metrics.barge_in.inc()),
        redactor=PiiRedactor(resolved),
        closed_snapshots=[],
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


def _container(request: Request) -> AppContainer:
    app = request.app
    if not isinstance(app, TurnwiseApp):
        raise RuntimeError("Turnwise routes mounted on an unexpected ASGI app")
    return app.container
