"""FastAPI authentication and authorization adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apyra.auth import (
    AuthenticationError,
    JWTAuthenticator,
    extract_scopes,
    get_auth_settings,
    has_role,
)

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Validate a bearer token and return its decoded payload."""

    if credentials is None and not request.cookies:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_authorization"
        )

    token: str | None = credentials.credentials if credentials is not None else None
    if token is None:
        settings = getattr(request.app.state, "auth_settings", None) or get_auth_settings()
        cookie_name = getattr(settings, "access_token_cookie", None) or "access_token"
        token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_authorization"
        )
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        settings = getattr(request.app.state, "auth_settings", None) or get_auth_settings()
        revocation_store = getattr(request.app.state, "revocation_store", None)
        authenticator = JWTAuthenticator(settings, revocation_store=revocation_store)
    try:
        decoded = authenticator.decode_token(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return decoded["payload"]


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
