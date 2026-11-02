"""Controlled fault-injection checks for Apyra release certification.

Restarts the disposable Redis and PostgreSQL containers mid-operation and verifies
the framework recovers. This runs against *isolated* test containers only — it
must never target production services.

Run::

    uv run python scripts/fault_injection.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time

REDIS_CONTAINER = "apyra-test-redis"
POSTGRES_CONTAINER = "apyra-test-postgres"


def _restart(container: str, wait: float = 2.0) -> None:
    # Controlled local test container; fixed "docker" path, no user input.
    subprocess.run(  # noqa: S603
        ["docker", "restart", container],  # noqa: S607
        check=True,
        capture_output=True,
    )
    time.sleep(wait)


async def check_redis_restart_recovery() -> bool:
    """A Redis Streams consumer must survive a Redis restart and resume processing."""
    import os

    import redis.asyncio as redis_async
    from apyra.messaging.contracts import DeliveryContext, MessageEnvelope
    from apyra.messaging.redis_streams import RedisStreamsConsumer, RedisStreamsPublisher

    url = os.environ.get("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")
    received: list[str] = []

    class Handler:
        async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
            received.append(str(envelope.message_id))

    client = redis_async.from_url(url, decode_responses=True)
    await client.flushdb()
    stream, group = "fault-stream", "fault-group"

    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"n": 1})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(client, stream, group, "worker", Handler(), block_ms=100)
    task = asyncio.create_task(consumer.run())

    # Restart Redis while the consumer is blocked on read.
    await asyncio.to_thread(_restart, REDIS_CONTAINER, 3.0)

    # Publish again after restart; the consumer loop must recover and process it.
    envelope2 = MessageEnvelope(payload={"n": 2})
    await publisher.publish(envelope2)
    for _ in range(100):
        if len(received) >= 1:
            break
        await asyncio.sleep(0.1)

    consumer.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await client.aclose()
    ok = len(received) >= 1
    print(f"redis-restart-recovery: processed={len(received)} -> {'PASS' if ok else 'FAIL'}")
    return ok


async def check_postgres_restart_recovery() -> bool:
    """A fresh session must connect successfully after a PostgreSQL restart."""
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get(
        "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
    )
    await asyncio.to_thread(_restart, POSTGRES_CONTAINER, 3.0)
    try:
        engine = create_async_engine(url, pool_pre_ping=True)
        async with engine.connect() as conn:
            value = (await conn.execute(text("SELECT 1"))).scalar_one()
        await engine.dispose()
        ok = value == 1
        print(f"postgres-restart-recovery: select1={value} -> {'PASS' if ok else 'FAIL'}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"postgres-restart-recovery: FAIL ({exc})")
        return False


async def main() -> int:
    results = [
        await check_redis_restart_recovery(),
        await check_postgres_restart_recovery(),
    ]
    if all(results):
        print("FAULT INJECTION: PASS")
        return 0
    print("FAULT INJECTION: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
