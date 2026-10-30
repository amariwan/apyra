"""Small thread-safe in-memory TTL cache with LRU eviction."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock


@dataclass(slots=True)
class _CacheEntry[V]:
    value: V
    expires_at: float


class MemoryTTLCache[K, V]:
    """Generic in-memory cache that can be reused across core and services."""

    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_entries: int = 256,
        enabled: bool = True,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._enabled = enabled and self._ttl_seconds > 0
        self._time_fn = time_fn or time.monotonic
        self._entries: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: K) -> V | None:
        if not self._enabled:
            return None

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= self._time_fn():
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry.value

    def set(self, key: K, value: V, *, ttl_seconds: int | None = None) -> V:
        if not self._enabled:
            return value

        ttl = self._ttl_seconds if ttl_seconds is None else max(0, ttl_seconds)
        expires_at = self._time_fn() + ttl
        with self._lock:
            self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
            self._entries.move_to_end(key)
            self._evict_if_needed()
        return value

    def get_or_set(self, key: K, factory: Callable[[], V]) -> V:
        cached = self.get(key)
        if cached is not None:
            return cached
        return self.set(key, factory())

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
