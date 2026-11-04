"""Redis-backed revocation store for multi-instance token revocation.

``TokenService`` is synchronous, so this store uses the synchronous ``redis``
client. It shares revocation state across every application instance pointed at
the same Redis database, enabling distributed token revocation and refresh-token
reuse detection without process-local state.

Family revocation is retained until the latest expiry of any linked token (tracked
through :meth:`register_family_token_expiration`), matching the in-memory store's
semantics so access tokens keep working until their natural expiry.
"""

from __future__ import annotations

import time
from math import ceil
from typing import Any


def _ttl(expires_at: float | None) -> int | None:
    """Return a Redis ``ex`` seconds value for a Unix expiry, or ``None`` for permanent."""
    if expires_at is None:
        return None
    return max(ceil(expires_at - time.time()), 1)


# Atomically consume a refresh token: returns 1 when the token is consumed (and
# neither the token nor its family was already revoked), or 0 when a reuse is
# detected. Using a Lua script makes concurrent rotation safe across instances.
_CONSUME_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 or redis.call('EXISTS', KEYS[2]) == 1 then
    local registered = tonumber(redis.call('GET', KEYS[3]) or '0')
    local requested = tonumber(ARGV[2])
    local latest = math.max(registered, requested)
    local current_ttl = redis.call('TTL', KEYS[2])
    if current_ttl ~= -1 then
        if latest > 0 then
            local now = redis.call('TIME')
            local ttl = math.max(math.ceil(latest - tonumber(now[1]) - tonumber(now[2]) / 1000000), 1)
            if ttl > current_ttl then
                redis.call('SET', KEYS[2], '1', 'EX', ttl)
            end
        elseif current_ttl == -2 then
            redis.call('SET', KEYS[2], '1')
        end
    end
    return 0
end
local ttl = tonumber(ARGV[1])
if ttl and ttl > 0 then
    redis.call('SET', KEYS[1], '1', 'EX', ttl)
else
    redis.call('SET', KEYS[1], '1')
end
return 1
"""

_REGISTER_EXPIRY_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local requested = tonumber(ARGV[1])
local latest = math.max(current, requested)
local now = redis.call('TIME')
local ttl = math.max(math.ceil(latest - tonumber(now[1]) - tonumber(now[2]) / 1000000), 1)
if ttl > 0 then
    redis.call('SET', KEYS[1], tostring(latest), 'EX', ttl)
else
    redis.call('SET', KEYS[1], tostring(latest))
end
if redis.call('EXISTS', KEYS[2]) == 1 then
    local family_ttl = redis.call('TTL', KEYS[2])
    if family_ttl ~= -1 and ttl and ttl > family_ttl then
        redis.call('SET', KEYS[2], '1', 'EX', ttl)
    end
end
return latest
"""

_REVOKE_FAMILY_SCRIPT = """
local requested = tonumber(ARGV[1])
local registered = tonumber(redis.call('GET', KEYS[1]) or '0')
local latest = math.max(requested, registered)
local current_ttl = redis.call('TTL', KEYS[2])
if current_ttl == -1 then
    return 1
end
local now = redis.call('TIME')
local ttl = math.max(math.ceil(latest - tonumber(now[1]) - tonumber(now[2]) / 1000000), 1)
if ttl > current_ttl then
    redis.call('SET', KEYS[2], '1', 'EX', ttl)
elseif current_ttl == -2 then
    if ttl and ttl > 0 then
        redis.call('SET', KEYS[2], '1', 'EX', ttl)
    else
        redis.call('SET', KEYS[2], '1')
    end
end
return latest
"""


class RedisRevocationStore:
    """Distributed token/family revocation store backed by Redis."""

    def __init__(self, client: Any, *, key_prefix: str = "apyra:revocation:") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _token_key(self, jti: str) -> str:
        return f"{self._key_prefix}token:{jti}"

    def _family_key(self, family_id: str) -> str:
        return f"{self._key_prefix}family:{family_id}"

    def _family_exp_key(self, family_id: str) -> str:
        return f"{self._key_prefix}family_exp:{family_id}"

    def revoke(self, jti: str, expires_at: float | None = None) -> None:
        """Revoke one token identifier, retaining it until its expiry if supplied."""
        self._client.set(self._token_key(jti), "1", ex=_ttl(expires_at))

    def revoke_family(self, family_id: str) -> None:
        """Revoke a refresh-token family permanently."""
        self._client.set(self._family_key(family_id), "1")

    def revoke_family_until(self, family_id: str, expires_at: float) -> None:
        """Revoke a refresh-token family until the supplied Unix timestamp."""
        self._client.eval(
            _REVOKE_FAMILY_SCRIPT,
            2,
            self._family_exp_key(family_id),
            self._family_key(family_id),
            str(expires_at),
        )

    def register_family_token_expiration(self, family_id: str, expires_at: float) -> None:
        """Track the latest linked-token expiry so family revocation outlives every token."""
        self._client.eval(
            _REGISTER_EXPIRY_SCRIPT,
            2,
            self._family_exp_key(family_id),
            self._family_key(family_id),
            str(expires_at),
        )

    def consume_refresh_token(self, jti: str, family_id: str) -> bool:
        """Atomically consume a refresh token, revoking its family on reuse."""
        return self._atomic_consume(jti, family_id, None)

    def consume_refresh_token_until(self, jti: str, family_id: str, expires_at: float) -> bool:
        """Consume a refresh token and expire its revocation with the token."""
        return self._atomic_consume(jti, family_id, expires_at)

    def _atomic_consume(self, jti: str, family_id: str, expires_at: float | None) -> bool:
        """Atomically check token/family revocation and consume the token."""
        ttl = _ttl(expires_at)
        consumed = self._client.eval(
            _CONSUME_SCRIPT,
            3,
            self._token_key(jti),
            self._family_key(family_id),
            self._family_exp_key(family_id),
            str(ttl) if ttl is not None else "0",
            str(expires_at or 0.0),
        )
        return bool(consumed == 1)

    def is_revoked(self, jti: str) -> bool:
        """Return whether a token identifier is currently revoked."""
        return bool(self._client.exists(self._token_key(jti)))

    def is_family_revoked(self, family_id: str) -> bool:
        """Return whether a refresh-token family is currently revoked."""
        return bool(self._client.exists(self._family_key(family_id)))
