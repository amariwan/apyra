"""Cache-backed Apyra FastAPI application.

Demonstrates the ``@cached`` decorator with an in-memory TTL cache.

Run with::

    uv run --project examples/cache-api uvicorn main:app \
      --app-dir examples/cache-api --reload
"""

from __future__ import annotations

import asyncio

from apyra.cache import cached, get_cache
from apyra.core import Settings
from apyra.fastapi import create_app

from fastapi import APIRouter


async def _expensive_lookup(key: str) -> dict:
    await asyncio.sleep(0.05)
    return {"key": key, "value": f"computed-for-{key}"}


@cached(ttl_seconds=60, key=lambda key: f"lookup:{key}")
async def lookup(key: str) -> dict:
    return await _expensive_lookup(key)


api = APIRouter()


@api.get("/lookup/{key}")
async def get_lookup(key: str) -> dict:
    return await lookup(key)


@api.get("/cache/size")
async def cache_size() -> dict:
    cache = get_cache()
    return {"backend": type(cache).__name__}


app = create_app(
    title="Cache Apyra API",
    routers=[api],
    settings=Settings(api_prefix="/api"),
)
