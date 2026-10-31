from fastapi.testclient import TestClient

from apyra.fastapi import TimingMiddleware, create_app, register_timing_middleware


def test_timing_middleware_adds_header() -> None:
    app = create_app()
    app.add_middleware(TimingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping")
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers


def test_register_timing_middleware_supports_custom_header_name() -> None:
    app = create_app()
    register_timing_middleware(app, header_name="X-Apyra-Elapsed")

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Apyra-Elapsed" in response.headers
    assert "X-Response-Time" not in response.headers
