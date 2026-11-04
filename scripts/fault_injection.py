"""Controlled fault-injection checks for Apyra release certification.

Restarts the disposable Redis and PostgreSQL containers mid-operation and verifies
the framework recovers. This runs against *isolated* test containers only — it
must never target production services.

Run::

    uv run python scripts/fault_injection.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import uuid4

_TEST_LABEL = "apyra.release-test-service"
logger = logging.getLogger(__name__)


def _log_check_failure(check_name: str, exc: Exception) -> None:
    """Log a fault-check failure without leaking arbitrary exception details."""
    logger.error("%s failed (%s)", check_name, type(exc).__name__)


def _verify_disposable_target(url: str, container: str, service: str) -> None:
    """Require a labeled disposable container and a local URL mapped to that container."""
    parsed = urlsplit(url)
    allowed_hosts = {"localhost", "127.0.0.1", "host.docker.internal"}
    expected_db = parsed.path.removeprefix("/")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"{service} URL must point to a local test service")
    if service == "redis" and expected_db != "15":
        raise ValueError("Redis fault injection requires the isolated database index 15")
    if service == "postgres" and not expected_db.endswith("_test"):
        raise ValueError("PostgreSQL fault injection requires a database ending in _test")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
        raise ValueError("container name must contain only safe Docker name characters")

    label = subprocess.run(  # noqa: S603 - fixed Docker inspection command
        [  # noqa: S607 - executable is fixed
            "docker",  # noqa: S607 - fixed executable; container name is validated above
            "inspect",
            f'--format={{{{ index .Config.Labels "{_TEST_LABEL}" }}}}',
            container,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    if label != service:
        raise ValueError(f"{service} container is not labeled as a disposable Apyra test service")

    internal_port = "6379/tcp" if service == "redis" else "5432/tcp"
    mappings = subprocess.run(  # noqa: S603 - fixed Docker inspection command
        ["docker", "port", container, internal_port],  # noqa: S607 - fixed executable
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.splitlines()
    mapped_ports = {line.rsplit(":", maxsplit=1)[-1].strip() for line in mappings}
    if parsed.port is None or str(parsed.port) not in mapped_ports:
        raise ValueError(f"{service} URL port does not map to the labeled test container")


def _restart(container: str, service: str, url: str, wait: float = 2.0) -> None:
    _verify_disposable_target(url, container, service)
    subprocess.run(  # noqa: S603
        ["docker", "restart", container],  # noqa: S607
        check=True,
        capture_output=True,
        timeout=90,
    )
    time.sleep(wait)


async def check_redis_restart_recovery(container: str) -> bool:
    """A Redis Streams consumer must survive a Redis restart and resume processing."""
    import redis.asyncio as redis_async
    from apyra.messaging.contracts import DeliveryContext, MessageEnvelope
    from apyra.messaging.redis_streams import RedisStreamsConsumer, RedisStreamsPublisher

    url = os.environ.get("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")
    _verify_disposable_target(url, container, "redis")
    received: list[str] = []

    class Handler:
        async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
            received.append(str(envelope.message_id))

    client = redis_async.from_url(url, decode_responses=True)
    stream, group = f"fault-stream-{uuid4().hex}", f"fault-group-{uuid4().hex}"

    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"n": 1})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(client, stream, group, "worker", Handler(), block_ms=100)
    task = asyncio.create_task(consumer.run())
    try:
        # Restart Redis while the consumer is blocked on read.
        await asyncio.to_thread(_restart, container, "redis", url, 3.0)

        # Publish again after restart; require this delivery to prove recovery.
        envelope2 = MessageEnvelope(payload={"n": 2})
        await publisher.publish(envelope2)
        expected_message_id = str(envelope2.message_id)
        for _ in range(100):
            if expected_message_id in received:
                break
            if task.done():
                task.result()
            await asyncio.sleep(0.1)

        ok = expected_message_id in received
        print(f"redis-restart-recovery: processed={len(received)} -> {'PASS' if ok else 'FAIL'}")
        return ok
    except Exception as exc:  # noqa: BLE001 - report infrastructure failures as failed checks
        _log_check_failure("redis-restart-recovery", exc)
        print("redis-restart-recovery: FAIL")
        return False
    finally:
        consumer.stop()
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - task failure was reported above
            _log_check_failure("redis-restart-recovery consumer task", exc)
        await client.aclose()


async def check_postgres_restart_recovery(container: str) -> bool:
    """A fresh session must connect successfully after a PostgreSQL restart."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get(
        "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
    )
    _verify_disposable_target(url, container, "postgres")
    await asyncio.to_thread(_restart, container, "postgres", url, 3.0)
    try:
        engine = create_async_engine(url, pool_pre_ping=True)
        async with engine.connect() as conn:
            value = (await conn.execute(text("SELECT 1"))).scalar_one()
        await engine.dispose()
        ok = value == 1
        print(f"postgres-restart-recovery: select1={value} -> {'PASS' if ok else 'FAIL'}")
        return ok
    except Exception as exc:  # noqa: BLE001
        _log_check_failure("postgres-restart-recovery", exc)
        print("postgres-restart-recovery: FAIL")
        return False


async def main() -> int:
    import argparse

    from apyra.observability import configure_logging

    parser = argparse.ArgumentParser(description="Run restart checks on labeled test containers.")
    parser.add_argument("--redis-container", required=True)
    parser.add_argument("--postgres-container", required=True)
    args = parser.parse_args()
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), json_output=True)
    results = [
        await check_redis_restart_recovery(args.redis_container),
        await check_postgres_restart_recovery(args.postgres_container),
    ]
    if all(results):
        print("FAULT INJECTION: PASS")
        return 0
    print("FAULT INJECTION: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
