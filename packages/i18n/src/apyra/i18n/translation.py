"""Translation manager and helpers."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any, cast

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]

from .context import get_locale

_manager: TranslationManager | None = None


class TranslationManager:
    """Resolve dotted translation keys from locale catalogs with fallback lookup."""

    def __init__(
        self,
        catalogs: dict[str, dict[str, Any]],
        default_locale: str = "en",
        fallback_locale: str = "en",
    ) -> None:
        """Create a manager from locale catalogs and locale fallback settings."""
        self.catalogs = catalogs
        self.default_locale = default_locale
        self.fallback_locale = fallback_locale

    @classmethod
    def from_directory(
        cls, directory: str | Path, default_locale: str = "en", fallback_locale: str = "en"
    ) -> TranslationManager:
        """Load one JSON object catalog per locale from the supplied directory."""
        path = Path(directory)
        catalogs: dict[str, dict[str, JsonValue]] = {}
        for file in path.glob("*.json"):
            with file.open(encoding="utf-8") as handle:
                catalog = json.load(handle)
            if not isinstance(catalog, dict):
                raise ValueError(  # noqa: TRY004
                    f"Translation catalog must be a JSON object: {file}"
                )
            catalogs[file.stem] = cast(dict[str, JsonValue], catalog)
        return cls(catalogs, default_locale=default_locale, fallback_locale=fallback_locale)

    def get(self, key: str, locale: str | None = None, **kwargs: Any) -> str:
        """Translate a dotted key, fall back to the fallback locale/key, and interpolate."""
        selected = locale or get_locale(self.default_locale)
        value = self._lookup(selected, key)
        if value is None and selected != self.fallback_locale:
            value = self._lookup(self.fallback_locale, key)
        if value is None:
            value = key
        if isinstance(value, str) and kwargs:
            return Template(value).safe_substitute(**kwargs)
        return str(value)

    def _lookup(self, locale: str, key: str) -> JsonValue | None:
        current: JsonValue | dict[str, JsonValue] = self.catalogs.get(locale, {})
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


def set_translation_manager(manager: TranslationManager) -> None:
    """Set the process-level manager used by ``translate`` helpers."""
    global _manager
    _manager = manager


def translate(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Translate a key through the configured manager, or return the key if unset."""
    if _manager is None:
        return key
    return _manager.get(key, locale=locale, **kwargs)
