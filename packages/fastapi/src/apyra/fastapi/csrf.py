"""CSRF protection for unsafe FastAPI requests."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from apyra.security import verify_csrf_token

from fastapi import HTTPException, Request, status

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def require_csrf(
    secret: str,
    *,
    csrf_cookie_name: str = "csrf_token",
    csrf_header_name: str = "X-CSRF-Token",
    binding_cookie_name: str | None = None,
) -> Callable[..., Awaitable[None]]:
    """Create a dependency that protects unsafe requests on opted-in routes.

    The application must issue the signed CSRF token in a script-readable cookie and
    require the client to send the same value in the configured header on every unsafe
    request to a route using this dependency. If a binding cookie name is set, the token
    must also be bound to that cookie's value.
    """

    if len(secret.encode("utf-8")) < 32:
        raise ValueError("CSRF secret must be at least 32 bytes")
    if not csrf_cookie_name or not csrf_header_name:
        raise ValueError("CSRF cookie and header names must not be empty")
    if binding_cookie_name == "":
        raise ValueError("CSRF binding cookie name must not be empty")

    async def dependency(request: Request) -> None:
        if request.method.upper() in _SAFE_METHODS:
            return

        cookie_token = request.cookies.get(csrf_cookie_name)
        header_token = request.headers.get(csrf_header_name)
        binding = (
            request.cookies.get(binding_cookie_name) if binding_cookie_name is not None else None
        )
        tokens_match = False
        if cookie_token and header_token:
            try:
                tokens_match = hmac.compare_digest(
                    cookie_token.encode("ascii"),
                    header_token.encode("ascii"),
                )
            except UnicodeEncodeError:
                tokens_match = False
        if (
            not cookie_token
            or not header_token
            or not tokens_match
            or (binding_cookie_name is not None and not binding)
            or not verify_csrf_token(header_token, secret, binding=binding)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="csrf_token_invalid",
            )

    return dependency


__all__ = ["require_csrf"]
