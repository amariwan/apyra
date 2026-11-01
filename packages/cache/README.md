# apyra-cache

Cache contracts and adapters for Apyra.

## Purpose

`apyra-cache` provides cache contracts, adapters (memory, Redis, Memcached), a `@cached` decorator, and factory helpers. Backends are optional extras.

## Installation

```bash
uv add apyra-cache                      # memory backend
uv add "apyra-cache[redis]"             # + Redis
uv add "apyra-cache[memcached]"        # + Memcached
```

## Minimal usage

```python
from apyra.cache import cached


@cached(ttl=60)
async def get_value(key: str) -> str: ...
```

## Optional dependencies

- `redis`: `redis>=5.0.0`
- `memcached`: `pymemcache>=4.0.0`

## Configuration

`CacheSettings` / `CacheBackend` via Pydantic Settings (`apyra.cache.settings`).

## Public API

- `AsyncCache`, `MemoryAsyncCache`, `MemoryTTLCache`, `RedisCache`, `MemcachedCache`
- `RedisClient`, `MemcachedClient`
- `cached`, `get_cache`, `close_cache`
- `CacheSettings`, `CacheBackend`, `get_cache_settings`
- `JSONValue`

## Error behavior

Cache backend errors propagate from the underlying client. Configuration errors raise during factory resolution.

## Integration

Use `get_cache()`/`close_cache()` in application lifespan. Combine with `apyra-fastapi` for request caching.

## Compatibility

- Python ≥ 3.12

## License

MIT
