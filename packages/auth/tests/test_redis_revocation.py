from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import SecretStr

from apyra.auth import AuthenticationError, AuthSettings, RedisRevocationStore, TokenService

REDIS_URL = os.getenv("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")


def _redis_available() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(REDIS_URL)
        client.ping()
        client.close()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.redis,
    pytest.mark.skipif(not _redis_available(), reason="Redis unavailable"),
]


def _settings() -> AuthSettings:
    return AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )


def test_redis_revocation_store_roundtrip() -> None:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    store = RedisRevocationStore(client)
    try:
        assert store.is_revoked("jti-1") is False
        store.revoke("jti-1")
        assert store.is_revoked("jti-1") is True
        assert store.is_family_revoked("fam-1") is False
        store.revoke_family("fam-1")
        assert store.is_family_revoked("fam-1") is True
    finally:
        client.flushdb()
        client.close()


def test_redis_refresh_token_consumption_detects_reuse() -> None:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    store = RedisRevocationStore(client)
    try:
        assert store.consume_refresh_token("jti-a", "fam-a") is True
        # Reuse of the same refresh token is rejected and revokes the family.
        assert store.consume_refresh_token("jti-a", "fam-a") is False
        assert store.is_family_revoked("fam-a") is True
    finally:
        client.flushdb()
        client.close()


def test_redis_token_service_rotation_and_reuse_detection() -> None:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    store = RedisRevocationStore(client)
    service = TokenService(_settings(), store=store)
    try:
        pair = service.issue_token_pair("user-1", scopes=["read"])
        rotated = service.rotate_refresh_token(pair.refresh_token)
        assert rotated.access_token and rotated.refresh_token

        # Reusing the already-rotated refresh token is detected and rejected.
        from apyra.auth import AuthenticationError

        with pytest.raises(AuthenticationError, match="token_reuse_detected"):
            service.rotate_refresh_token(pair.refresh_token)
        with pytest.raises(AuthenticationError, match="token_revoked"):
            service.verify_access_token(rotated.access_token)
    finally:
        client.flushdb()
        client.close()


def test_redis_token_revocation_until_expiry() -> None:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    store = RedisRevocationStore(client)
    try:
        future = time.time() + 60
        store.revoke("jti-timed", expires_at=future)
        assert store.is_revoked("jti-timed") is True
    finally:
        client.flushdb()
        client.close()


def test_redis_family_revocation_keeps_latest_expiry() -> None:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    store = RedisRevocationStore(client)
    family_id = "family-latest-expiry"
    try:
        latest_expiry = time.time() + 300
        store.register_family_token_expiration(family_id, latest_expiry)
        store.revoke_family_until(family_id, time.time() + 60)
        assert store.is_family_revoked(family_id)
        assert client.ttl(store._family_key(family_id)) > 200

        store.register_family_token_expiration(family_id, time.time() + 600)
        assert client.ttl(store._family_key(family_id)) > 500
    finally:
        client.flushdb()
        client.close()


def test_concurrent_refresh_rotation_yields_single_success() -> None:
    """Concurrent rotation of the same refresh token must admit exactly one winner."""
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.flushdb()
    service = TokenService(_settings(), store=RedisRevocationStore(client))
    try:
        pair = service.issue_token_pair("user-1", scopes=["read"])

        def rotate() -> bool:
            try:
                service.rotate_refresh_token(pair.refresh_token)
                return True
            except AuthenticationError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: rotate(), range(8)))

        assert sum(outcomes) == 1
        # The refresh token is now consumed; any further rotation is rejected.
        with pytest.raises(AuthenticationError, match="token_reuse_detected"):
            service.rotate_refresh_token(pair.refresh_token)
    finally:
        client.flushdb()
        client.close()
