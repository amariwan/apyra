"""Locale context management."""

from __future__ import annotations

import contextvars
from contextvars import Token
from typing import Self

_locale: contextvars.ContextVar[str] = contextvars.ContextVar("apyra_locale", default="en")


def get_locale() -> str:
    return _locale.get()


def set_locale(value: str) -> None:
    _locale.set(value)


class LocaleContext:
    def __init__(self, value: str) -> None:
        self._value = value
        self._token: Token[str] | None = None

    def __enter__(self) -> Self:
        self._token = _locale.set(self._value)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _locale.reset(self._token)
