"""Cache contracts and adapters for Apyra."""

from __future__ import annotations

from .async_cache import AsyncCache, JSONValue, MemoryAsyncCache
from .decorators import cached
from .factory import close_cache, get_cache
from .memcached_cache import MemcachedCache, MemcachedClient
from .memory_cache import MemoryTTLCache
from .redis_cache import RedisCache, RedisClient
from .settings import CacheBackend, CacheSettings, get_cache_settings

__all__ = [
    "AsyncCache",
    "CacheBackend",
    "CacheSettings",
    "JSONValue",
    "MemcachedCache",
    "MemcachedClient",
    "MemoryAsyncCache",
    "MemoryTTLCache",
    "RedisCache",
    "RedisClient",
    "cached",
    "close_cache",
    "get_cache",
    "get_cache_settings",
]
