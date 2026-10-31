"""Locale context management."""

from __future__ import annotations

import contextvars
from contextvars import Token
from typing import Self

_locale: contextvars.ContextVar[str | None] = contextvars.ContextVar("apyra_locale", default=None)


def get_locale(default: str = "en") -> str:
    """Return the active locale, or ``default`` when this context has none."""
    return _locale.get() or default


def set_locale(value: str) -> None:
    """Set the locale for the current context and its async descendants."""
    _locale.set(value)


class LocaleContext:
    """Temporarily select a locale and restore the prior context on exit."""

    def __init__(self, value: str) -> None:
        """Create a context manager for the supplied locale identifier."""
        self._value = value
        self._token: Token[str | None] | None = None

    def __enter__(self) -> Self:
        """Set this locale and return the context manager."""
        self._token = _locale.set(self._value)
        return self

    def __exit__(self, *exc: object) -> None:
        """Restore the locale that was active before entering this context."""
        if self._token is not None:
            _locale.reset(self._token)
