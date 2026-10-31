"""Secret comparison and redaction helpers."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from typing import Any, cast

_REDACTED = "***REDACTED***"
_SENSITIVE_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "credential",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def constant_time_compare(left: str, right: str) -> bool:
    """Compare two strings using a timing-resistant equality check."""
    return hmac.compare_digest(left, right)


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return redact_mapping(cast(Mapping[str, Any], value))
    if isinstance(value, list):
        return [_redact_value(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in cast(tuple[object, ...], value))
    return value


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a mapping while masking sensitive keys in nested containers."""
    result: dict[str, Any] = {}
    for key, item in value.items():
        if _is_sensitive_key(str(key)):
            result[str(key)] = _REDACTED
        else:
            result[str(key)] = _redact_value(item)
    return result
