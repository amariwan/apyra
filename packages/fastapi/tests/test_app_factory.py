from apyra.core import Settings
from fastapi.testclient import TestClient

from apyra.fastapi import create_app


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
