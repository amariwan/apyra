from typing import TypedDict

import pytest
from apyra.core import Settings
from fastapi.testclient import TestClient

from apyra.fastapi import create_app


class RateLimitOptions(TypedDict, total=False):
    rate_limit_max_requests: int
    rate_limit_window_seconds: int


def test_create_app_health_endpoint() -> None:
    app = create_app(title="Test API", settings=Settings(app_name="Test API"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Test API"}


def test_create_app_registers_router() -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/hello")
    async def hello() -> dict[str, str]:
        return {"message": "hello"}

    app = create_app(routers=[router], settings=Settings(api_prefix="/api"))

    with TestClient(app) as client:
        response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello"}


def test_create_app_is_repeatable() -> None:
    first = create_app()
    second = create_app()

    assert first is not second
    assert first.title == second.title == "Apyra API"


def test_create_app_adds_security_headers_by_default() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "geolocation=()"


def test_create_app_preserves_existing_security_header() -> None:
    from fastapi import APIRouter
    from fastapi.responses import Response

    router = APIRouter()

    @router.get("/custom")
    async def custom() -> Response:
        return Response(content="ok", headers={"X-Frame-Options": "SAMEORIGIN"})

    app = create_app(routers=[router], settings=Settings(api_prefix=""))

    with TestClient(app) as client:
        response = client.get("/custom")

    # The route's own value is preserved; only unset headers are added.
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_create_app_can_disable_security_headers() -> None:
    app = create_app(security_headers=False)

    with TestClient(app) as client:
        response = client.get("/health")

    assert "X-Frame-Options" not in response.headers
    assert "X-Content-Type-Options" not in response.headers


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"rate_limit_max_requests": 0}, "rate_limit_max_requests must be positive"),
        ({"rate_limit_window_seconds": 0}, "rate_limit_window_seconds must be positive"),
    ],
)
def test_create_app_rejects_invalid_enabled_rate_limit(
    options: RateLimitOptions, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        create_app(rate_limit_enabled=True, **options)


def test_create_app_rate_limit_returns_429_after_limit() -> None:
    app = create_app(
        rate_limit_enabled=True,
        rate_limit_max_requests=1,
        rate_limit_window_seconds=60,
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/health")

    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_startup_failure_runs_shutdown_hooks() -> None:
    calls: list[str] = []

    def startup(_app: object) -> None:
        calls.append("startup")
        raise ValueError("startup failed")

    def shutdown(_app: object) -> None:
        calls.append("shutdown")

    app = create_app(startup=[startup], shutdown=[shutdown])
    with pytest.raises(ValueError, match="startup failed"), TestClient(app):
        pass

    assert calls == ["startup", "shutdown"]


def test_all_shutdown_hooks_run_when_one_fails() -> None:
    calls: list[str] = []

    def failing_shutdown(_app: object) -> None:
        calls.append("first")
        raise ValueError("cleanup failed")

    def final_shutdown(_app: object) -> None:
        calls.append("second")

    app = create_app(shutdown=[failing_shutdown, final_shutdown])
    with pytest.raises(BaseExceptionGroup), TestClient(app):
        pass

    assert calls == ["first", "second"]
