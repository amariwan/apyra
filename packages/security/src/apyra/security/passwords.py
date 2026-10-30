"""Password hashing using PBKDF2."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ITERATIONS = 390000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return (
        "pbkdf2_sha256$"
        + base64.b64encode(salt).decode("ascii")
        + "$"
        + base64.b64encode(digest).decode("ascii")
    )


def verify_password(password: str, hashed: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = hashed.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(digest_b64.encode("ascii"))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)
