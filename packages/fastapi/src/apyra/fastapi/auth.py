"""FastAPI authentication and authorization adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

from apyra.auth import (
    AuthenticationError,
    JWTAuthenticator,
    extract_scopes,
    get_auth_settings,
    has_role,
)

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme: HTTPBearer = HTTPBearer(auto_error=False)


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Validate a bearer token and return its decoded payload."""

    if credentials is None and not request.cookies:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_authorization"
        )

    settings = getattr(request.app.state, "auth_settings", None) or get_auth_settings()
    token: str | None = credentials.credentials if credentials is not None else None
    if token is None:
        cookie_name = getattr(settings, "access_token_cookie", "access_token")
        if cookie_name is not None:
            token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_authorization"
        )
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        revocation_store = getattr(request.app.state, "revocation_store", None)
        authenticator = JWTAuthenticator(settings, revocation_store=revocation_store)
    try:
        decode_access_token = getattr(authenticator, "decode_access_token", None)
        decode_method = (
            decode_access_token if callable(decode_access_token) else authenticator.decode_token
        )
        decoded = cast(dict[str, Any], await asyncio.to_thread(decode_method, token))
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    payload = cast(dict[str, Any], decoded["payload"])
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="access_token_required"
        )
    expected_access_token_type = getattr(settings, "expected_access_token_type", None)
    if expected_access_token_type is not None and payload.get("type") != expected_access_token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_type_invalid")
    expected_header_typ = getattr(settings, "expected_access_token_header_typ", None)
    header = decoded.get("header")
    header_typ = cast(dict[str, Any], header).get("typ") if isinstance(header, dict) else None
    if expected_header_typ is not None and header_typ != expected_header_typ:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token_header_type_invalid"
        )
    return payload


def require_scopes(*scopes: str) -> Callable[[dict[str, Any]], Any]:
    """Require all supplied OAuth2 scopes."""

    async def dependency(payload: dict[str, Any] = Depends(get_current_token)) -> dict[str, Any]:
        granted = extract_scopes(payload)
        missing = [scope for scope in scopes if scope not in granted]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"missing_scopes": missing},
            )
        return payload

    return dependency


def require_roles(
    *roles: str, hierarchy: dict[str, set[str]] | None = None
) -> Callable[[dict[str, Any]], Any]:
    """Require all supplied roles."""

    async def dependency(payload: dict[str, Any] = Depends(get_current_token)) -> dict[str, Any]:
        missing = [role for role in roles if not has_role(payload, role, hierarchy=hierarchy)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"missing_roles": missing},
            )
        return payload

    return dependency


def get_current_user(payload: dict[str, Any] = Depends(get_current_token)) -> dict[str, Any]:
    """Alias for bearer-token authentication."""

    return payload
