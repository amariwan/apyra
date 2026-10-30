# apyra-cache

Cache contracts, adapters, and decorators for Apyra.

## Installation

```bash
uv add apyra-cache
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

## License

MIT