"""Fixtures for the stage runtime. Each test gets its own registry and tracer."""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from pipeline.metrics import StageMetrics, build_stage_metrics
from pipeline.session import Session, SessionStore
from pipeline.stage import CleanupHook, Stage, StageConfig, StageHandler
from server.config import Settings

SESSION_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="turnwise-test",
        log_level="WARNING",
        log_json=False,
        http_host="127.0.0.1",
        http_port=8000,
        stage_queue_maxsize=8,
        stage_put_timeout_s=0.25,
        otel_enabled=False,
        otel_endpoint="http://127.0.0.1:4317",
        otel_insecure=True,
        otel_export_timeout_s=1.0,
        otel_max_queue_size=128,
        metrics_enabled=True,
        pii_hash_key=SecretStr("test-key"),
        pii_fields="patient_name,name,dob,date_of_birth,phone",
        vad_onnx_path="models/weights/missing.onnx",
        vad_timeout_ms=200,
        turn_onnx_path="models/weights/missing.onnx",
        turn_model_enabled=False,
        nlu_model_path="",
    )


@dataclass(slots=True)
class Harness:
    """One in-memory tracer, metric registry, and session."""

    settings: Settings
    metrics: StageMetrics
    tracer: Tracer
    exporter: InMemorySpanExporter
    store: SessionStore
    session: Session
    config: StageConfig
    _provider: TracerProvider

    def stage(
        self,
        name: str,
        handler: StageHandler,
        *,
        on_cleanup: CleanupHook | None = None,
        session_id: str | None = None,
        config: StageConfig | None = None,
    ) -> Stage:
        return Stage(
            name=name,
            session_id=self.session.session_id if session_id is None else session_id,
            sessions=self.store,
            handler=handler,
            config=self.config if config is None else config,
            tracer=self.tracer,
            metrics=self.metrics,
            on_cleanup=on_cleanup,
        )

    def shutdown(self) -> None:
        self._provider.shutdown()


@pytest.fixture
def harness(settings: Settings) -> Iterator[Harness]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    metrics = build_stage_metrics(CollectorRegistry())
    store = SessionStore(on_barge_in=lambda: metrics.barge_in.inc())
    built = Harness(
        settings=settings,
        metrics=metrics,
        tracer=provider.get_tracer("turnwise-test"),
        exporter=exporter,
        store=store,
        session=store.open(SESSION_ID),
        config=StageConfig(
            queue_maxsize=settings.stage_queue_maxsize,
            put_timeout_s=settings.stage_put_timeout_s,
        ),
        _provider=provider,
    )
    try:
        yield built
    finally:
        built.shutdown()
