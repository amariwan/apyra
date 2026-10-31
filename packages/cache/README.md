# apyra-cache

Cache contracts, adapters, and decorators for Apyra.

## Installation

```bash
uv add apyra-cache
uv add 'apyra-cache[redis]'     # Redis backend
uv add 'apyra-cache[memcached]' # Memcached backend
```

## Quick usage

```python
from apyra.cache import cached


@cached(ttl_seconds=60)
async def get_user(user_id: str) -> dict:
    return {"id": user_id}
```

## Key exports

- `cached` — async cache decorator
- `AsyncCache`, `MemoryAsyncCache`, `MemoryTTLCache`
- `RedisCache`, `MemcachedCache`
- `get_cache`, `close_cache`, `get_cache_settings`

Set `CacheSettings(cache_enabled=False)` to make cache operations no-ops without initializing the
selected backend.

The default decorator key includes the function name and a SHA-256 digest of the normalized
argument representation instead of argument values in plaintext. This is not a keyed digest: do
not cache functions that accept passwords or other low-entropy secrets with the default key,
because an attacker with access to backend keys could test guesses offline. Avoid caching those
functions or provide an application-managed keyed cache key that preserves all
result-distinguishing inputs.

## Memcached scope

`MemcachedCache.clear()` uses Memcached's server-wide `flush_all`, so it invalidates keys outside
the configured key prefix too. This operation is disabled by default. Enable it only for a
dedicated Memcached server with `CACHE_MEMCACHED_ALLOW_SERVER_FLUSH=true`; calling `clear()` without
that explicit setting raises `RuntimeError`. Avoid enabling it when unrelated applications share
the server.

## License

MIT
