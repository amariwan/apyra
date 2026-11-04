from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from apyra.observability import configure_opentelemetry, get_tracer, span
from apyra.observability.telemetry import _sqlalchemy_is_instrumentable


def test_configure_opentelemetry_sets_provider() -> None:
    configure_opentelemetry("test-service")
    tracer = get_tracer("test")
    assert tracer is not None


def test_span_records() -> None:
    configure_opentelemetry("test-service")
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    from typing import Any, cast

    cast(Any, provider).add_span_processor(SimpleSpanProcessor(exporter))
    with span("work"):
        pass
    spans = exporter.get_finished_spans()
    assert any(s.name == "work" for s in spans)


def test_sqlalchemy_instrumentability_matches_installed_version() -> None:
    pytest.importorskip("sqlalchemy")
    import importlib.metadata

    version = importlib.metadata.version("sqlalchemy")
    major, minor = (int(part) for part in version.split(".")[:2])
    expected = (major, minor) < (2, 1)
    assert _sqlalchemy_is_instrumentable() is expected
