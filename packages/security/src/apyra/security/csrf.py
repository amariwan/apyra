"""CSRF token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_csrf_token(secret: str) -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(secret.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def verify_csrf_token(token: str, secret: str) -> bool:
    try:
        nonce, signature = token.split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(secret.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
