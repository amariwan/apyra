"""Event-bus-backed Apyra FastAPI application.

Demonstrates publishing and subscribing to typed events with the in-memory bus.

Run with::

    uv run uvicorn main:app --app-dir examples/events-api --reload
"""

from __future__ import annotations

from apyra.core import Settings
from apyra.events import Event, InMemoryEventBus
from apyra.fastapi import create_app

from fastapi import APIRouter

bus = InMemoryEventBus()
received: list[dict] = []


async def _on_user_created(event: Event) -> None:
    received.append(event.payload)


bus.subscribe("user.created", _on_user_created)

api = APIRouter()


@api.post("/users")
async def create_user(name: str) -> dict:
    event = Event(name="user.created", payload={"name": name})
    errors = await bus.publish(event)
    return {"name": name, "published": True, "errors": [str(e) for e in errors]}


@api.get("/events/received")
async def list_received() -> dict:
    return {"count": len(received), "items": received}


app = create_app(
    title="Events Apyra API",
    routers=[api],
    settings=Settings(api_prefix="/api"),
)
