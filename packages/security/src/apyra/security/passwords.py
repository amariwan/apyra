"""Password hashing using PBKDF2."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_LEGACY_ITERATIONS = 390_000
_ITERATIONS = 600_000
_MAX_VERIFY_ITERATIONS = 2_000_000


def hash_password(password: str) -> str:
    """Hash a password as a salted PBKDF2-SHA256 string for storage."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return (
        f"pbkdf2_sha256${_ITERATIONS}$"
        + base64.b64encode(salt).decode("ascii")
        + "$"
        + base64.b64encode(digest).decode("ascii")
    )


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against this module's PBKDF2-SHA256 format."""
    parts = hashed.split("$")
    if len(parts) == 3:
        algorithm, salt_b64, digest_b64 = parts
        iterations = _LEGACY_ITERATIONS
    elif len(parts) == 4:
        algorithm, iterations_text, salt_b64, digest_b64 = parts
        if (
            len(iterations_text) > len(str(_MAX_VERIFY_ITERATIONS))
            or not iterations_text.isascii()
            or not iterations_text.isdecimal()
        ):
            return False
        iterations = int(iterations_text)
        if not _LEGACY_ITERATIONS <= iterations <= _MAX_VERIFY_ITERATIONS:
            return False
    else:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return False
    if len(salt) != 16 or len(expected) != hashlib.sha256().digest_size:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def password_hash_needs_rehash(hashed: str) -> bool:
    """Return whether a stored hash should be replaced after successful verification."""
    parts = hashed.split("$")
    if len(parts) != 4:
        return True
    algorithm, iterations_text, salt_b64, digest_b64 = parts
    if algorithm != "pbkdf2_sha256":
        return True
    if (
        len(iterations_text) > len(str(_MAX_VERIFY_ITERATIONS))
        or not iterations_text.isascii()
        or not iterations_text.isdecimal()
    ):
        return True
    if int(iterations_text) != _ITERATIONS:
        return True
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        digest = base64.b64decode(digest_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return True
    return len(salt) != 16 or len(digest) != hashlib.sha256().digest_size
