from fastapi import APIRouter
from fastapi.testclient import TestClient

from apyra.fastapi import cbv, get, post


def test_class_based_view_registers_routes() -> None:
    router = APIRouter()

    @cbv(router)
    class ItemView:
        @get("/items/{item_id}")
        async def get_item(self, item_id: int, q: str | None = None) -> dict[str, object]:
            return {"item_id": item_id, "q": q}

        @post("/items")
        async def create_item(self, name: str) -> dict[str, str]:
            return {"name": name}

    from apyra.fastapi import create_app

    app = create_app(routers=[router])
    with TestClient(app) as client:
        response = client.get("/items/42?q=search")
        assert response.status_code == 200
        assert response.json() == {"item_id": 42, "q": "search"}

        response = client.post("/items?name=widget")
        assert response.status_code == 200
        assert response.json() == {"name": "widget"}
