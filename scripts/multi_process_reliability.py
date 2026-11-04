"""Multi-OS-process reliability harness for Apyra release certification.

Spawns real OS processes (not threads/tasks) that contend on shared Redis and
PostgreSQL state, then asserts the framework's atomicity guarantees hold across
process boundaries.

Run (requires Redis + PostgreSQL)::

    APYRA_TEST_REDIS_URL=redis://localhost:6379/15 \
uv run python scripts/multi_process_reliability.py --redis-container apyra-test-redis --processes 8

Each check prints ``PASS``/``FAIL``; the process exits non-zero on any failure.

At-least-once delivery is assumed; these checks verify atomic *consumption*
(exactly one winner), never end-to-end exactly-once processing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from multiprocessing import Pool


def _issue_pair() -> tuple[str, str]:
    import redis
    from apyra.auth import AuthSettings, RedisRevocationStore, TokenService
    from pydantic import SecretStr

    client = redis.Redis.from_url(
        os.environ.get("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15"),
        decode_responses=True,
    )
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("multi-process-secret-with-at-least-32-bytes"),
        algorithms=["HS256"],
        issuer="apyra-harness",
        audience="apyra-harness-api",
    )
    service = TokenService(settings, store=RedisRevocationStore(client))
    pair = service.issue_token_pair("subject-1", scopes=["read"])
    client.close()
    return pair.access_token, pair.refresh_token


def _rotate_worker(refresh_token: str) -> int:
    """One process rotates the shared refresh token; returns 1 on success, 0 on reuse."""
    import redis
    from apyra.auth import AuthenticationError, AuthSettings, RedisRevocationStore, TokenService
    from pydantic import SecretStr

    client = redis.Redis.from_url(
        os.environ.get("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15"),
        decode_responses=True,
    )
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("multi-process-secret-with-at-least-32-bytes"),
        algorithms=["HS256"],
        issuer="apyra-harness",
        audience="apyra-harness-api",
    )
    service = TokenService(settings, store=RedisRevocationStore(client))
    try:
        service.rotate_refresh_token(refresh_token)
        return 1
    except AuthenticationError:
        return 0
    finally:
        client.close()


def _claim_worker(message_id: str) -> int:
    """One process claims the shared idempotency key; returns 1 on CLAIMED, 0 otherwise."""
    import uuid

    import redis.asyncio as redis_async
    from apyra.messaging.idempotency import ClaimResult, RedisIdempotencyStore

    async def run() -> int:
        client = redis_async.from_url(
            os.environ.get("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15"),
            decode_responses=True,
        )
        store = RedisIdempotencyStore(client)
        try:
            result = await store.claim(uuid.UUID(message_id))
            return 1 if result is ClaimResult.CLAIMED else 0
        finally:
            await client.aclose()

    return asyncio.run(run())


def check_concurrent_refresh(processes: int) -> bool:
    """N processes rotate the same refresh token; exactly one must win."""
    _access, refresh = _issue_pair()
    with Pool(processes) as pool:
        results = pool.map(_rotate_worker, [refresh] * processes)
    winners = sum(results)
    ok = winners == 1
    verdict = "PASS" if ok else "FAIL"
    print(f"concurrent-refresh-rotation ({processes} processes): winners={winners} -> {verdict}")
    return ok


def check_concurrent_idempotency(processes: int) -> bool:
    """N processes claim the same idempotency key; exactly one must be CLAIMED."""
    import uuid

    message_id = str(uuid.uuid4())
    with Pool(processes) as pool:
        results = pool.map(_claim_worker, [message_id] * processes)
    winners = sum(results)
    ok = winners == 1
    verdict = "PASS" if ok else "FAIL"
    print(f"concurrent-idempotency-claim ({processes} processes): winners={winners} -> {verdict}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=8)
    parser.add_argument("--redis-container", required=True)
    args = parser.parse_args()

    redis_url = os.environ.get("APYRA_TEST_REDIS_URL")
    if redis_url is None:
        parser.error("APYRA_TEST_REDIS_URL must target a disposable test service")
    from fault_injection import _verify_disposable_target

    try:
        _verify_disposable_target(redis_url, args.redis_container, "redis")
    except Exception as exc:  # noqa: BLE001 - fail closed without exposing subprocess output
        parser.error(f"unsafe Redis test target: {type(exc).__name__}")
    if args.processes < 2:
        parser.error("--processes must be at least 2")

    checks = [
        check_concurrent_refresh(args.processes),
        check_concurrent_idempotency(args.processes),
    ]
    if all(checks):
        print("MULTI-PROCESS RELIABILITY: PASS")
        return 0
    print("MULTI-PROCESS RELIABILITY: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
