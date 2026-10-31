"""Structured logging configuration."""

from __future__ import annotations

import contextvars
import json
import logging
import re
from collections.abc import Mapping
from typing import Any, cast

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "apyra_request_id", default=None
)
_REDACTED = "***REDACTED***"
_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "cookie", "api_key", "apikey"}
_SECRET_PATTERN = re.compile(
    r"(?i)(?P<prefix>(?:password|secret|token|api[_-]?key)[\"']?\s*[:=]\s*)"
    r"(?:(?P<quote>[\"'])(?:\\.|(?!(?P=quote))[\s\S])*(?P=quote)|[^\s,;]+)"
)
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)(?:(?:bearer|basic)\s+)?[^\s,;\"']+"
)
_JSON_COOKIE_PATTERN = re.compile(
    r'(?i)(?P<prefix>"(?P<name>set-cookie|set_cookie|cookie)"\s*:\s*")(?P<value>[^"]*)(?P<suffix>")'
)
_PYTHON_COOKIE_PATTERN = re.compile(
    r"(?i)(?P<prefix>['\"](?P<name>set-cookie|set_cookie|cookie)['\"]\s*:\s*(?:b)?(?P<quote>['\"]))"
    r"(?P<value>.*?)(?P<suffix>(?P=quote))"
)
_PYTHON_RAW_COOKIE_PAIR_PATTERN = re.compile(
    r"(?i)(?P<prefix>b['\"](?:set-cookie|cookie)['\"]\s*,\s*b(?P<quote>['\"]))"
    r"(?P<value>(?:\\.|(?!(?P=quote))[\s\S])*)(?P=quote)(?=\s*[,\])])"
)
_PYTHON_COOKIE_BYTEARRAY_PATTERN = re.compile(
    r"(?i)(?P<prefix>['\"](?:set-cookie|cookie)['\"]\s*:\s*bytearray\(b(?P<quote>['\"]))"
    r"(?P<value>(?:\\.|(?!(?P=quote))[\s\S])*)(?P=quote)\)"
)
_PYTHON_COOKIE_CONTAINER_PATTERN = re.compile(
    r"(?i)(?P<prefix>['\"](?:set-cookie|cookie)['\"]\s*:\s*)(?P<open>[\[{(])"
)
_COOKIE_HEADER_PATTERN = re.compile(
    r"(?i)(?P<prefix>(?P<name>\b(?:set-cookie|cookie))\s*:\s*)(?P<value>[^\r\n\"]*)"
)
_COOKIE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?P<prefix>\b(?:set-)?cookie\s*=\s*)(?P<value>[^\s,;]+)"
)


def set_request_id(value: str | None) -> None:
    """Set or clear the request ID in the current asynchronous context."""
    _request_id.set(value)


def get_request_id() -> str | None:
    """Return the request ID set in the current asynchronous context, if any."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Format log records as JSON while redacting common credential values."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a record with level, logger, message, request ID, and exception."""
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": _redacted_message(record),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_redact(payload), default=str)


def _redact_string(value: str) -> str:
    value = _AUTHORIZATION_PATTERN.sub(lambda match: f"{match.group(1)}{_REDACTED}", value)
    value = _JSON_COOKIE_PATTERN.sub(_redact_cookie_match, value)
    value = _redact_python_cookie_containers(value)
    value = _PYTHON_COOKIE_PATTERN.sub(_redact_cookie_match, value)
    value = _PYTHON_RAW_COOKIE_PAIR_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{_REDACTED}{match.group('quote')}", value
    )
    value = _PYTHON_COOKIE_BYTEARRAY_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{_REDACTED}{match.group('quote')})", value
    )
    value = _COOKIE_HEADER_PATTERN.sub(_redact_cookie_match, value)
    value = _COOKIE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{_REDACTED}", value
    )
    return _SECRET_PATTERN.sub(_redact_secret_match, value)


def _redact_secret_match(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    quote = match.group("quote")
    if quote:
        return f"{prefix}{quote}{_REDACTED}{quote}"
    return f"{prefix}{_REDACTED}"


def _redacted_message(record: logging.LogRecord) -> str:
    message_value = record.msg if isinstance(record.msg, str) else _redact(record.msg)
    message = str(message_value)
    if record.args:
        message %= _redact(record.args)
    return _redact_string(message)


def _redact_python_cookie_containers(value: str) -> str:
    output: list[str] = []
    cursor = 0
    for match in _PYTHON_COOKIE_CONTAINER_PATTERN.finditer(value):
        opener = match.group("open")
        closer_by_opener = {"[": "]", "{": "}", "(": ")"}
        stack = [closer_by_opener[opener]]
        quote: str | None = None
        escaped = False
        index = match.end()
        while index < len(value) and stack:
            char = value[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in "'\"":
                quote = char
            elif char in closer_by_opener:
                stack.append(closer_by_opener[char])
            elif char == stack[-1]:
                stack.pop()
            index += 1
        if stack:
            continue
        output.extend((value[cursor : match.start()], match.group("prefix"), _REDACTED))
        cursor = index
    if not output:
        return value
    output.append(value[cursor:])
    return "".join(output)


def _redact_cookie_match(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    header_name = match.group("name").lower()
    redact_all_pairs = header_name == "cookie"
    parts = match.group("value").split(";")
    pair_count = len(parts) if redact_all_pairs else min(1, len(parts))
    for index in range(pair_count):
        part = parts[index]
        leading_space = part[: len(part) - len(part.lstrip())]
        pair = part[len(leading_space) :]
        name, separator, _ = pair.partition("=")
        parts[index] = (
            f"{leading_space}{name}={_REDACTED}"
            if separator and name.strip()
            else f"{leading_space}{_REDACTED}"
        )
    suffix = match.groupdict().get("suffix", "")
    return f"{prefix}{';'.join(parts)}{suffix}"


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in cast(Mapping[object, object], value).items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key in _SENSITIVE_KEYS or any(
                sensitive in normalized_key for sensitive in _SENSITIVE_KEYS
            ):
                result[str(key)] = _REDACTED
            else:
                result[str(key)] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in cast(tuple[object, ...], value))
    if isinstance(value, str):
        return _redact_string(value)
    return value


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    """Configure root logging and replace its handlers with one formatted stream."""
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
