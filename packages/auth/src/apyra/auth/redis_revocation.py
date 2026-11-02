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
from typing import Any


def _ttl(expires_at: float | None) -> int | None:
    """Return a Redis ``ex`` seconds value for a Unix expiry, or ``None`` for permanent."""
    if expires_at is None:
        return None
    return max(int(expires_at - time.time()), 1)


# Atomically consume a refresh token: returns 1 when the token is consumed (and
# neither the token nor its family was already revoked), or 0 when a reuse is
# detected. Using a Lua script makes concurrent rotation safe across instances.
_CONSUME_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 or redis.call('EXISTS', KEYS[2]) == 1 then
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
        self._client.set(self._family_key(family_id), "1", ex=_ttl(expires_at))

    def register_family_token_expiration(self, family_id: str, expires_at: float) -> None:
        """Track the latest linked-token expiry so family revocation outlives every token."""
        key = self._family_exp_key(family_id)
        current = self._client.get(key)
        current_value = float(current) if current is not None else 0.0
        new_value = max(current_value, expires_at)
        self._client.set(key, str(new_value), ex=_ttl(new_value))

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
            2,
            self._token_key(jti),
            self._family_key(family_id),
            str(ttl) if ttl is not None else "0",
        )
        if consumed == 1:
            return True
        # Reuse detected: revoke the whole family (best-effort, not atomic).
        self.revoke_family_until(family_id, self._family_expiry(family_id, expires_at or 0.0))
        return False

    def _family_expiry(self, family_id: str, fallback: float) -> float:
        current = self._client.get(self._family_exp_key(family_id))
        if current is None:
            return fallback
        return max(float(current), fallback)

    def is_revoked(self, jti: str) -> bool:
        """Return whether a token identifier is currently revoked."""
        return bool(self._client.exists(self._token_key(jti)))

    def is_family_revoked(self, family_id: str) -> bool:
        """Return whether a refresh-token family is currently revoked."""
        return bool(self._client.exists(self._family_key(family_id)))
