import asyncio

import pytest

from apyra.channels import MemoryChannelLayer


@pytest.mark.asyncio
async def test_publish_subscribe() -> None:
    layer = MemoryChannelLayer()
    subscription = await layer.subscribe("events")
    task = asyncio.create_task(anext(subscription))
    await asyncio.sleep(0)
    await layer.publish("events", {"hello": "world"})
    result = await asyncio.wait_for(task, timeout=1)
    assert result == {"hello": "world"}
    await subscription.close()
