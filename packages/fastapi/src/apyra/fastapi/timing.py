"""Timing middleware for Apyra FastAPI applications."""

from __future__ import annotations

import time
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add an ``X-Response-Time`` header to every response."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        typed_response = cast(Response, response)
        typed_response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        return typed_response


def register_timing_middleware(app: Any, *, header_name: str = "X-Response-Time") -> None:
    """Register timing middleware with a custom response header name."""

    class _TimingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            started_at = time.perf_counter()
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            typed_response = cast(Response, response)
            typed_response.headers[header_name] = f"{elapsed_ms:.2f}ms"
            return typed_response

    app.add_middleware(_TimingMiddleware)
