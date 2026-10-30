"""Translation manager and helpers."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

from .context import get_locale

_manager: TranslationManager | None = None


class TranslationManager:
    def __init__(
        self,
        catalogs: dict[str, dict[str, Any]],
        default_locale: str = "en",
        fallback_locale: str = "en",
    ) -> None:
        self.catalogs = catalogs
        self.default_locale = default_locale
        self.fallback_locale = fallback_locale

    @classmethod
    def from_directory(
        cls, directory: str | Path, default_locale: str = "en", fallback_locale: str = "en"
    ) -> TranslationManager:
        path = Path(directory)
        catalogs: dict[str, dict[str, Any]] = {}
        for file in path.glob("*.json"):
            with file.open(encoding="utf-8") as handle:
                catalogs[file.stem] = json.load(handle)
        return cls(catalogs, default_locale=default_locale, fallback_locale=fallback_locale)

    def get(self, key: str, locale: str | None = None, **kwargs: Any) -> str:
        selected = locale or get_locale() or self.default_locale
        value = self._lookup(selected, key)
        if value is None and selected != self.fallback_locale:
            value = self._lookup(self.fallback_locale, key)
        if value is None:
            value = key
        if isinstance(value, str) and kwargs:
            return Template(value).safe_substitute(**kwargs)
        return str(value)

    def _lookup(self, locale: str, key: str) -> Any:
        current: Any = self.catalogs.get(locale, {})
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


def set_translation_manager(manager: TranslationManager) -> None:
    global _manager
    _manager = manager


def translate(key: str, locale: str | None = None, **kwargs: Any) -> str:
    if _manager is None:
        return key
    return _manager.get(key, locale=locale, **kwargs)
