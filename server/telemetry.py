"""OpenTelemetry bootstrap. The provider is owned by the app, not the global tracer."""

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from server.config import Settings


@dataclass(slots=True)
class Tracing:
    """A tracer plus the provider that must be shut down with the process."""

    provider: TracerProvider
    tracer: Tracer

    def shutdown(self) -> None:
        self.provider.shutdown()


def start_tracing(settings: Settings) -> Tracing:
    """Build a tracer. Export is enabled only when ``otel_enabled`` is set.

    The SDK batch queue is bounded (``otel_max_queue_size``). When the collector
    is down the exporter drops spans after that queue fills; the voice process
    keeps running. The global tracer provider is left unset so tests can build
    more than one app in a single interpreter.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
    if settings.otel_enabled:
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_endpoint,
            insecure=settings.otel_insecure,
            timeout=settings.otel_export_timeout_s,
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_queue_size=settings.otel_max_queue_size,
                max_export_batch_size=min(512, settings.otel_max_queue_size),
                export_timeout_millis=int(settings.otel_export_timeout_s * 1000),
                schedule_delay_millis=500,
            )
        )
    return Tracing(provider=provider, tracer=provider.get_tracer("turnwise"))
