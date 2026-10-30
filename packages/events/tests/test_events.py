import pytest

from apyra.events import Event, InMemoryEventBus


@pytest.mark.asyncio
async def test_event_bus_calls_handlers() -> None:
    bus = InMemoryEventBus()
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(str(event.payload["value"]))

    bus.subscribe("created", handler)
    errors = await bus.publish(Event(name="created", payload={"value": "ok"}))

    assert errors == []
    assert seen == ["ok"]
