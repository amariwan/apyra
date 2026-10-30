"""Secret comparison and redaction helpers."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from typing import Any

_REDACTED = "***REDACTED***"
_SENSITIVE_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "credential",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if _is_sensitive_key(str(key)):
            result[str(key)] = _REDACTED
        elif isinstance(item, Mapping):
            result[str(key)] = redact_mapping(item)
        elif isinstance(item, list):
            result[str(key)] = [redact_mapping(x) if isinstance(x, Mapping) else x for x in item]
        else:
            result[str(key)] = item
    return result
