from fastapi.testclient import TestClient

from apyra.fastapi import TimingMiddleware, create_app


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
