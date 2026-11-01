"""Optional OpenTelemetry integration for Apyra."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, cast

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # pragma: no cover
    trace = None  # type: ignore
    Resource = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore


def configure_opentelemetry(service_name: str, otlp_endpoint: str | None = None) -> None:
    """Configure a global tracer provider when OpenTelemetry is installed."""
    if TracerProvider is None or Resource is None or trace is None:
        raise RuntimeError("OpenTelemetry is required")
    resource_cls = Resource
    provider_cls = TracerProvider
    resource = resource_cls.create({"service.name": service_name})
    provider = provider_cls(resource=resource)
    if (
        otlp_endpoint is not None
        and OTLPSpanExporter is not None
        and BatchSpanProcessor is not None
    ):
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    cast(Any, trace).set_tracer_provider(provider)


def get_tracer(name: str) -> Any:
    if trace is None:
        raise RuntimeError("OpenTelemetry is required")
    tracer_provider = cast(Any, trace)
    return tracer_provider.get_tracer(name)


@contextmanager
def span(name: str, tracer_name: str = "apyra") -> Generator[Any, None, None]:
    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(name) as current_span:
        yield current_span


def instrument_fastapi(app: Any) -> bool:
    """Instrument a FastAPI app if the optional instrumentation package is installed."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return False
    FastAPIInstrumentor.instrument_app(app)
    return True


def instrument_sqlalchemy(engine: Any) -> bool:
    """Instrument a SQLAlchemy engine if the optional instrumentation package is installed."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return False
    SQLAlchemyInstrumentor().instrument(engine=engine)
    return True
