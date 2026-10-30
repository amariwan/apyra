"""Application factory for Apyra FastAPI apps."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from apyra.core import Settings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from fastapi import FastAPI
from fastapi.responses import JSONResponse

StartupHook = Callable[[FastAPI], Awaitable[None] | None]
ShutdownHook = Callable[[FastAPI], Awaitable[None] | None]


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip()
    if not prefix:
        return ""
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix.rstrip("/")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=()")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        if self.max_requests <= 0 or self.window_seconds <= 0:
            return await call_next(request)

        client_host = request.client.host if request.client is not None else "unknown"
        now = time.monotonic()
        async with self._lock:
            # Drop stale client buckets to avoid unbounded memory growth.
            stale_clients = [
                key
                for key, values in self._requests.items()
                if not values or now - values[-1] >= self.window_seconds
            ]
            for key in stale_clients:
                del self._requests[key]

            timestamps = [
                timestamp
                for timestamp in self._requests[client_host]
                if now - timestamp < self.window_seconds
            ]
            if len(timestamps) >= self.max_requests:
                self._requests[client_host] = timestamps
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])) + 1)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)
            self._requests[client_host] = timestamps

        return await call_next(request)


def create_app(
    *,
    title: str = "Apyra API",
    version: str = "0.1.0",
    description: str | None = None,
    routers: Sequence[Any] = (),
    settings: Settings | None = None,
    startup: Sequence[StartupHook] = (),
    shutdown: Sequence[ShutdownHook] = (),
    health_path: str = "/health",
    security_headers: bool = True,
    rate_limit_enabled: bool = False,
    rate_limit_max_requests: int = 100,
    rate_limit_window_seconds: int = 60,
) -> FastAPI:
    """Create a FastAPI application with Apyra defaults.

    The function is pure with respect to global state: it does not read or mutate
    process-wide singletons and can be called repeatedly in tests.
    """

    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for hook in startup:
            result = hook(app)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]
        try:
            yield
        finally:
            for hook in shutdown:
                result = hook(app)
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]

    app = FastAPI(
        title=title,
        version=version,
        description=description or "",
        lifespan=lifespan,
    )

    api_prefix = _normalize_prefix(resolved_settings.normalized_api_prefix())
    origins = resolved_settings.cors_allowed_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if security_headers:
        app.add_middleware(SecurityHeadersMiddleware)

    if rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=rate_limit_max_requests,
            window_seconds=rate_limit_window_seconds,
        )

    if health_path:
        normalized_health_path = health_path if health_path.startswith("/") else f"/{health_path}"

        @app.get(normalized_health_path, tags=["health"])
        async def health() -> dict[str, str]:
            return {"status": "ok", "service": resolved_settings.app_name}

    for router in routers:
        app.include_router(router, prefix=api_prefix)

    return app
