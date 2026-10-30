"""Async cache decorators for Apyra."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .factory import get_cache

T = TypeVar("T")
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def _make_key(
    func: Callable[..., Any],
    key: str | Callable[..., str] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    if callable(key):
        value = key(*args, **kwargs)
    elif isinstance(key, str):
        value = key
    else:
        value = f"{func.__qualname__}:{args!r}:{sorted(kwargs.items())!r}"
    return str(value)


def cached(
    *,
    ttl_seconds: int | None = None,
    key: str | Callable[..., str] | None = None,
) -> Callable[[_F], _F]:
    """Cache the result of an async function.

    The cached value is wrapped internally so that ``None`` results are
    distinguishable from cache misses. Values must be compatible with the
    selected cache backend (JSON-compatible for Redis/Memcached).
    """

    def decorator(func: _F) -> _F:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"@cached requires an async function, got {func!r}")

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_cache()
            cache_key = _make_key(func, key, args, kwargs)
            cached_payload = await cache.get(cache_key)
            if isinstance(cached_payload, dict) and cached_payload.get("__apyra_cached__") is True:
                return cached_payload.get("value")
            result = await func(*args, **kwargs)
            await cache.set(
                cache_key,
                {"__apyra_cached__": True, "value": result},
                ttl_seconds=ttl_seconds,
            )
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["cached"]
