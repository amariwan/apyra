"""Lazy cache backend selection."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Protocol, cast

from .async_cache import AsyncCache, MemoryAsyncCache
from .memcached_cache import MemcachedCache, MemcachedClient
from .settings import CacheBackend, get_cache_settings


class _RedisFactory(Protocol):
    """Redis constructor interface used to keep the dependency optional."""

    def from_url(self, url: str | None, *, decode_responses: bool) -> object:
        """Create a Redis client from a URL and response-decoding setting."""
        ...


@lru_cache(maxsize=1)
def get_cache() -> AsyncCache:
    """Return the cached backend selected by current cache settings."""
    settings = get_cache_settings()
    if not settings.cache_enabled:
        return MemoryAsyncCache(ttl_seconds=0, max_entries=settings.cache_max_entries)
    if settings.cache_backend is CacheBackend.MEMORY:
        return MemoryAsyncCache(
            ttl_seconds=settings.cache_default_ttl_seconds,
            max_entries=settings.cache_max_entries,
        )

    if settings.cache_backend is CacheBackend.MEMCACHED:
        try:
            import pymemcache.client.base as memcached_module  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
        except ModuleNotFoundError as exc:
            if exc.name != "pymemcache":
                raise
            raise RuntimeError("Memcached cache requires the 'pymemcache' project extra") from exc
        servers = settings.cache_memcached_servers or "localhost:11211"
        host, separator, port = servers.partition(":")
        address = (host, int(port)) if separator else (host, 11211)
        memcached_client = cast(MemcachedClient, memcached_module.Client(address))
        return MemcachedCache(
            memcached_client,
            key_prefix=settings.cache_key_prefix,
            default_ttl_seconds=settings.cache_default_ttl_seconds,
            allow_server_flush=settings.cache_memcached_allow_server_flush,
        )

    try:
        redis_factory = cast(_RedisFactory, vars(import_module("redis.asyncio"))["Redis"])
    except ModuleNotFoundError as exc:
        if exc.name != "redis":
            raise
        raise RuntimeError("Redis cache requires the 'redis' project extra") from exc

    from .redis_cache import RedisCache, RedisClient

    redis_client = cast(
        RedisClient, redis_factory.from_url(settings.cache_redis_url, decode_responses=False)
    )
    return RedisCache(
        redis_client,
        key_prefix=settings.cache_key_prefix,
        default_ttl_seconds=settings.cache_default_ttl_seconds,
    )


async def close_cache() -> None:
    """Close the cached backend if it was initialized."""

    if get_cache.cache_info().currsize == 0:
        return
    cache = get_cache()
    await cache.close()
    get_cache.cache_clear()


__all__ = ["close_cache", "get_cache"]
