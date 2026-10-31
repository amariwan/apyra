"""Async cache decorators for Apyra."""

from __future__ import annotations

import functools
import hashlib
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from .factory import get_cache

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def _make_key(
    func: Callable[..., Any],
    key: str | Callable[..., str] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    signature: inspect.Signature,
) -> str:
    if callable(key):
        value = key(*args, **kwargs)
    elif isinstance(key, str):
        value = key
    else:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        arguments_hash = hashlib.sha256(repr(bound.arguments).encode("utf-8")).hexdigest()
        value = f"{func.__module__}.{func.__qualname__}:{arguments_hash}"
    return str(value)


def cached(
    *,
    ttl_seconds: int | None = None,
    key: str | Callable[..., str] | None = None,
) -> Callable[[_F], _F]:
    """Cache the result of an async function.

    The cached value is wrapped internally so that ``None`` results are
    distinguishable from cache misses. Values must be compatible with the
    selected cache backend (JSON-compatible for Redis/Memcached). The default
    key hashes argument representations, but is not a keyed digest; do not use
    it for functions that accept passwords or other low-entropy secrets.
    """

    def decorator(func: _F) -> _F:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"@cached requires an async function, got {func!r}")
        signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_cache()
            cache_key = _make_key(func, key, args, kwargs, signature)
            cached_payload = await cache.get(cache_key)
            if isinstance(cached_payload, dict):
                payload = cast(dict[str, Any], cached_payload)
                if payload.get("__apyra_cached__") is True and "value" in payload:
                    return payload["value"]
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
