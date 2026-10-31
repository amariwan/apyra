"""CSRF token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_csrf_token(secret: str, *, binding: str | None = None) -> str:
    """Create a CSRF token, optionally bound to an application-owned session value."""

    key = _csrf_key(secret)
    nonce = secrets.token_urlsafe(32)
    message = _csrf_message(nonce.encode("utf-8"), binding)
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def verify_csrf_token(token: str, secret: str, *, binding: str | None = None) -> bool:
    """Verify a token, returning false for malformed values or mismatched bindings."""
    try:
        nonce, signature = token.split(".", 1)
        supplied = signature.encode("ascii")
        nonce_bytes = nonce.encode("utf-8")
        secret_bytes = _csrf_key(secret)
        message = _csrf_message(nonce_bytes, binding)
    except (ValueError, UnicodeEncodeError):
        return False
    expected = hmac.new(secret_bytes, message, hashlib.sha256).hexdigest().encode("ascii")
    return hmac.compare_digest(supplied, expected)


def _csrf_key(secret: str) -> bytes:
    key = secret.encode("utf-8")
    if len(key) < 32:
        raise ValueError("CSRF secret must be at least 32 bytes")
    return key


def _csrf_message(nonce: bytes, binding: str | None) -> bytes:
    if binding is None:
        return nonce
    binding_bytes = binding.encode("utf-8")
    if not binding_bytes:
        raise ValueError("CSRF token binding must not be empty")
    binding_length = len(binding_bytes).to_bytes(8, byteorder="big")
    return b"apyra-csrf-binding\x00" + binding_length + binding_bytes + nonce
