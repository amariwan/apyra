"""Cross-package integration test: auth + fastapi."""

from __future__ import annotations

import time
from datetime import datetime, tzinfo

import jwt
import pytest
from apyra.auth import AuthenticationError, AuthSettings, JWTAuthenticator, TokenService
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
            "iss": "apyra-tests",
            "aud": "apyra-api",
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
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    authenticator = JWTAuthenticator(settings)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/scopes")
    async def scopes(
        payload: dict[str, object] = Depends(require_scopes("read", "write")),  # noqa: B008
    ) -> dict[str, object]:
        return payload

    @app.get("/roles")
    async def roles(
        payload: dict[str, object] = Depends(require_roles("admin")),  # noqa: B008
    ) -> dict[str, object]:
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
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    store = TokenService(settings).store
    authenticator = JWTAuthenticator(settings, revocation_store=store)

    app = FastAPI()
    app.state.authenticator = authenticator
    app.state.revocation_store = store

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(require_scopes("read")),  # noqa: B008
    ) -> dict[str, object]:
        return payload

    token = _make_token(["read"], ["user"])
    TokenService(settings, store=store).revoke(token)

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


@pytest.mark.parametrize("revoke_refresh", [False, True])
def test_revocation_stays_effective_through_jwt_expiration_leeway(
    monkeypatch: pytest.MonkeyPatch,
    revoke_refresh: bool,
) -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
        clock_skew_secs=10,
    )
    now = int(time.time())
    clock = [float(now)]

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return datetime.fromtimestamp(clock[0], tz=tz)

    monkeypatch.setattr("apyra.auth.tokens.time.time", lambda: clock[0])
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDateTime)

    service = TokenService(settings)
    authenticator = JWTAuthenticator(settings, revocation_store=service.store)
    pair = service.issue_token_pair("user-1", access_expires_in=5, refresh_expires_in=5)
    service.revoke(pair.refresh_token if revoke_refresh else pair.access_token)
    clock[0] = float(now + 6)

    with pytest.raises(AuthenticationError, match="token_revoked"):
        authenticator.decode_access_token(pair.access_token)
