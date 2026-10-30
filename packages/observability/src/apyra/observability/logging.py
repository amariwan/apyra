"""Structured logging configuration."""

from __future__ import annotations

import contextvars
import json
import logging
import re
from collections.abc import Mapping
from typing import Any

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "apyra_request_id", default=None
)
_REDACTED = "***REDACTED***"
_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "api_key", "apikey"}
_SECRET_PATTERN = re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*([^\s,;]+)")


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_string(record.getMessage()),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_redact(payload), default=str)


def _redact_string(value: str) -> str:
    return _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}={_REDACTED}", value)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                result[str(key)] = _REDACTED
            else:
                result[str(key)] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
