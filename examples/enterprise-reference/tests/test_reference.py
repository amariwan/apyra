from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    token_resp = client.post("/api/auth/token", params={"customer_id": "cust-1"})
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_order() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post("/api/orders", params={"customer_id": "cust-1"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "created"


def test_get_order() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        created = client.post("/api/orders", params={"customer_id": "cust-1"}, headers=headers)
        order_id = created.json()["order_id"]
        response = client.get(f"/api/orders/{order_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["customer_id"] == "cust-1"


def test_process_order_workflow() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        created = client.post("/api/orders", params={"customer_id": "cust-1"}, headers=headers)
        order_id = created.json()["order_id"]
        response = client.post(f"/api/orders/{order_id}/process", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_unauthorized_order_create() -> None:
    with TestClient(app) as client:
        response = client.post("/api/orders", params={"customer_id": "cust-1"})
    assert response.status_code == 401


def _redis_available() -> bool:
    try:
        import redis.asyncio as r

        async def check() -> bool:
            client = r.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            try:
                await client.ping()
                return True
            except Exception:  # noqa: BLE001
                return False
            finally:
                await client.aclose()

        import asyncio

        return asyncio.run(check())
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _redis_available(), reason="Redis unavailable")
def test_publish_and_consume() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        client.post("/api/orders", params={"customer_id": "cust-1"}, headers=headers)
        pub = client.post("/api/publish-pending")
        assert pub.status_code == 200
        assert pub.json()["published"] >= 1
        cons = client.post("/api/consume")
        assert cons.status_code == 200
