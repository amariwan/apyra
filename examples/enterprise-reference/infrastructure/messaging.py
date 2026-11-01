"""Redis messaging helpers for the reference application."""

from __future__ import annotations

import json

import redis.asyncio as redis_async
from apyra.messaging.contracts import MessageEnvelope
from apyra.messaging.outbox import OutboxMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def publish_pending_outbox(session: AsyncSession, redis_url: str) -> int:
    """Publish pending outbox messages to Redis Streams and mark them delivered."""
    client = redis_async.from_url(redis_url, decode_responses=True)
    result = await session.execute(select(OutboxMessage).where(OutboxMessage.status == "pending"))
    messages = list(result.scalars().all())
    published = 0
    for message in messages:
        envelope = MessageEnvelope(message_id=message.id, payload=message.payload)
        await client.xadd(
            "orders",
            {"message_id": str(envelope.message_id), "payload": json.dumps(envelope.payload)},
        )
        message.status = "delivered"
        published += 1
    await session.commit()
    await client.aclose()
    return published
