"""Helpers for localizing validation errors."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .translation import translate


def translate_validation_errors(
    errors: Iterable[Mapping[str, Any]],
    *,
    locale: str | None = None,
) -> list[dict[str, Any]]:
    """Translate Pydantic-style validation errors using the active catalog.

    Each input item is expected to contain at least ``type`` and ``msg`` keys.
    The function looks up ``validation.<type>`` and falls back to the original
    message when no translation exists.
    """

    translated: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        error_type = str(item.get("type", ""))
        key = f"validation.{error_type}" if error_type else ""
        message = translate(key, locale=locale) if key else str(item.get("msg", ""))
        if message == key:
            message = str(item.get("msg", ""))
        item["msg"] = message
        translated.append(item)
    return translated


__all__ = ["translate_validation_errors"]
