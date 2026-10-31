"""Tests for FastAPI monitoring middleware."""

from __future__ import annotations

import pytest
from apyra.observability import InMemoryErrorReporter, set_error_reporter
from fastapi.testclient import TestClient

from apyra.fastapi import create_app, register_monitoring_middleware


def test_performance_monitoring_middleware_adds_header() -> None:
    app = create_app(performance_monitoring=True)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Response-Time" in response.headers


def test_error_monitoring_middleware_captures_exception() -> None:
    reporter = InMemoryErrorReporter()
    set_error_reporter(reporter)
    app = create_app(error_monitoring=True)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise ValueError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert len(reporter.events()) == 1
    assert reporter.events()[0].message == "boom"


def test_register_monitoring_middleware() -> None:
    app = create_app()
    register_monitoring_middleware(app)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Response-Time" in response.headers


@pytest.fixture(autouse=True)
def _reset_monitoring_state() -> None:
    from apyra.observability import PerformanceMonitor, set_error_reporter, set_performance_monitor
    from apyra.observability.errors import InMemoryErrorReporter

    set_error_reporter(InMemoryErrorReporter())
    set_performance_monitor(PerformanceMonitor())


def test_error_monitoring_config_validation() -> None:
    from apyra.fastapi.monitoring import ErrorMonitoringConfig, PerformanceMonitoringConfig

    with pytest.raises(ValueError):
        ErrorMonitoringConfig(level="invalid")
    with pytest.raises(ValueError):
        PerformanceMonitoringConfig(header_name="")
    with pytest.raises(ValueError):
        PerformanceMonitoringConfig(metric_name="")


def test_combined_registrar_disable_flags() -> None:
    app = create_app()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    register_monitoring_middleware(app, performance=False)

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Response-Time" not in response.headers


def test_combined_registrar_prefix_arguments() -> None:
    app = create_app()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    register_monitoring_middleware(
        app,
        performance_header_name="X-Custom-Elapsed",
        error_level="warning",
    )

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Custom-Elapsed" in response.headers


def test_combined_registrar_unknown_argument() -> None:
    app = create_app()
    with pytest.raises(TypeError):
        register_monitoring_middleware(app, not_a_real_option=True)


def test_combined_registrar_both_configs() -> None:
    from apyra.fastapi.monitoring import ErrorMonitoringConfig, PerformanceMonitoringConfig

    app = create_app()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    register_monitoring_middleware(
        app,
        error_config=ErrorMonitoringConfig(level="warning"),
        performance_config=PerformanceMonitoringConfig(header_name="X-Both"),
    )

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Both" in response.headers
