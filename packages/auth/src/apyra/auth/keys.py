"""JWKS key provider."""

from __future__ import annotations

from functools import lru_cache

import jwt


@lru_cache(maxsize=1)
def _cached_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url)


def get_jwks_client() -> jwt.PyJWKClient:
    from .settings import get_auth_settings

    settings = get_auth_settings()
    if not settings.jwks_url:
        raise RuntimeError("AUTH_JWKS_URL missing")
    return _cached_client(str(settings.jwks_url))


def reset_jwks_client() -> None:
    _cached_client.cache_clear()
