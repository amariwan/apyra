"""API key generation and verification."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_api_key(prefix: str = "apyra") -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    key = f"{prefix}_{secret}"
    hashed = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return key, hashed


def verify_api_key(key: str, hashed: str) -> bool:
    actual = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return hmac.compare_digest(actual, hashed)
