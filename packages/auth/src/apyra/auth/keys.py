"""JWKS key provider."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

import jwt


@lru_cache(maxsize=1)
def _cached_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url)


def get_jwks_client(url: str | None = None) -> jwt.PyJWKClient:
    """Return a cached PyJWT JWKS client after requiring an HTTPS URL."""
    if url is None:
        from .settings import get_auth_settings

        jwks_url = get_auth_settings().jwks_url
        if not jwks_url:
            raise RuntimeError("AUTH_JWKS_URL missing")
        url = str(jwks_url)
    parsed_url = urlsplit(url)
    if parsed_url.scheme.lower() != "https":
        raise RuntimeError("JWKS URL must use HTTPS")
    if parsed_url.username is not None or parsed_url.password is not None:
        raise RuntimeError("JWKS URL cannot contain user information")
    return _cached_client(url)


def reset_jwks_client() -> None:
    """Clear the cached JWKS client after key endpoint configuration changes."""
    _cached_client.cache_clear()
