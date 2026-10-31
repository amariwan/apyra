from __future__ import annotations

from typing import Any

import pytest

from apyra.cache import decorators


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> Any | None:
        return self.values.get(key)

    async def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self.values[key] = value
        self.ttls[key] = ttl_seconds

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def clear(self) -> None:
        self.values.clear()

    async def close(self) -> None:
        await self.clear()


@pytest.mark.asyncio
async def test_cached_decorator_stores_and_reuses_result(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)
    calls = 0

    @decorators.cached(ttl_seconds=45, key="answer")
    async def calculate(value: int) -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"result": value}

    assert await calculate(42) == {"result": 42}
    assert await calculate(42) == {"result": 42}
    assert calls == 1
    assert cache.ttls == {"answer": 45}


@pytest.mark.asyncio
async def test_cached_decorator_caches_none(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)
    calls = 0

    @decorators.cached()
    async def lookup(item_id: int) -> None:
        nonlocal calls
        calls += 1

    assert await lookup(7) is None
    assert await lookup(7) is None
    assert calls == 1


@pytest.mark.asyncio
async def test_cached_decorator_recomputes_incomplete_cache_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)
    calls = 0

    @decorators.cached(key="answer")
    async def calculate() -> str:
        nonlocal calls
        calls += 1
        return "fresh"

    cache.values["answer"] = {"__apyra_cached__": True}

    assert await calculate() == "fresh"
    assert calls == 1
    assert cache.values["answer"] == {"__apyra_cached__": True, "value": "fresh"}


@pytest.mark.asyncio
async def test_default_cache_key_normalizes_positional_and_keyword_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)
    calls = 0

    @decorators.cached()
    async def combine(left: int, right: int = 0) -> int:
        nonlocal calls
        calls += 1
        return left + right

    assert await combine(2, right=3) == 5
    assert await combine(left=2, right=3) == 5
    assert await combine(2) == 2
    assert await combine(left=2, right=0) == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_default_cache_key_separates_same_qualified_name_across_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)

    async def first(value: int) -> str:
        return "first"

    async def second(value: int) -> str:
        return "second"

    second.__qualname__ = first.__qualname__
    first.__module__ = "package.first"
    second.__module__ = "package.second"
    first_cached = decorators.cached()(first)
    second_cached = decorators.cached()(second)

    assert await first_cached(1) == "first"
    assert await second_cached(1) == "second"


@pytest.mark.asyncio
async def test_callable_cache_key_receives_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)

    def cache_key(user_id: int) -> str:
        return f"user:{user_id}"

    @decorators.cached(key=cache_key)
    async def lookup(user_id: int) -> str:
        return f"user-{user_id}"

    assert await lookup(9) == "user-9"
    assert "user:9" in cache.values


@pytest.mark.asyncio
async def test_default_cache_key_preserves_variadic_keyword_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)
    calls = 0

    @decorators.cached()
    async def options(**values: int) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return tuple(values)

    assert await options(alpha=1, beta=2) == ("alpha", "beta")
    assert await options(beta=2, alpha=1) == ("beta", "alpha")
    assert calls == 2


@pytest.mark.asyncio
async def test_default_cache_key_does_not_expose_argument_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeCache()
    monkeypatch.setattr(decorators, "get_cache", lambda: cache)

    @decorators.cached()
    async def lookup(token: str) -> str:
        return "result"

    await lookup("secret-token-value")

    assert len(cache.values) == 1
    stored_key = next(iter(cache.values))
    assert stored_key.startswith(
        "test_decorators.test_default_cache_key_does_not_expose_argument_values.<locals>.lookup:"
    )
    assert "secret-token-value" not in stored_key


def test_cached_decorator_rejects_sync_functions() -> None:
    def calculate() -> int:
        return 1

    with pytest.raises(TypeError, match="requires an async function"):
        decorators.cached()(calculate)  # type: ignore[arg-type]
