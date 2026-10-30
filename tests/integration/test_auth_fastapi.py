"""Cross-package integration test: auth + fastapi."""

from __future__ import annotations

import time

import jwt
import pytest
from apyra.auth import AuthSettings, JWTAuthenticator, TokenService
from apyra.fastapi import require_roles, require_scopes
from fastapi.testclient import TestClient
from pydantic import SecretStr

from fastapi import Depends, FastAPI

SECRET = "integration-test-secret-with-enough-length"  # noqa: S105


def _make_token(scopes: list[str], roles: list[str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "type": "access",
            "jti": "integration-token",
            "scopes": scopes,
            "roles": roles,
        },
        SECRET,
        algorithm="HS256",
    )


@pytest.mark.integration
def test_auth_fastapi_cross_package() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(SECRET), algorithms=["HS256"], issuer=None, audience=None
    )
    authenticator = JWTAuthenticator(settings)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/scopes")
    async def scopes(payload=Depends(require_scopes("read", "write"))) -> dict:  # noqa: B008, type: ignore[no-untyped-def]
        return payload

    @app.get("/roles")
    async def roles(payload=Depends(require_roles("admin"))) -> dict:  # noqa: B008, type: ignore[no-untyped-def]
        return payload

    with TestClient(app) as client:
        token = _make_token(["read", "write"], ["admin"])
        assert (
            client.get("/scopes", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        )

        token = _make_token(["read"], ["admin"])
        assert (
            client.get("/scopes", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        )

        token = _make_token(["read"], ["user"])
        assert client.get("/roles", headers={"Authorization": f"Bearer {token}"}).status_code == 403


@pytest.mark.integration
def test_revoked_token_rejected_cross_package() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(SECRET), algorithms=["HS256"], issuer=None, audience=None
    )
    store = TokenService(settings).store
    authenticator = JWTAuthenticator(settings, revocation_store=store)

    app = FastAPI()
    app.state.authenticator = authenticator
    app.state.revocation_store = store

    @app.get("/protected")
    async def protected(payload=Depends(require_scopes("read"))) -> dict:  # noqa: B008, type: ignore[no-untyped-def]
        return payload

    token = _make_token(["read"], ["user"])
    TokenService(settings, store=store).revoke(token)

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
