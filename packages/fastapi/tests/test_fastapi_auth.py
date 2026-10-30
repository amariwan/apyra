import time

import jwt
from apyra.auth import AuthSettings, JWTAuthenticator, TokenService
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from apyra.fastapi import require_roles, require_scopes

SECRET = "secret-with-enough-length-for-hs256"


def make_token(scopes: list[str], roles: list[str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "type": "access",
            "jti": "token-1",
            "scopes": scopes,
            "roles": roles,
        },
        SECRET,
        algorithm="HS256",
    )


def test_fastapi_auth_dependencies() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(SECRET), algorithms=["HS256"], issuer=None, audience=None
    )
    authenticator = JWTAuthenticator(settings)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/scopes")
    async def scopes(payload=Depends(require_scopes("read", "write"))) -> dict[str, object]:
        return payload

    @app.get("/roles")
    async def roles(payload=Depends(require_roles("admin"))) -> dict[str, object]:
        return payload

    with TestClient(app) as client:
        token = make_token(["read", "write"], ["admin"])
        response = client.get("/scopes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        token = make_token(["read"], ["admin"])
        response = client.get("/scopes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

        token = make_token(["read"], ["user"])
        response = client.get("/roles", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


def test_revoked_token_is_rejected() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(SECRET), algorithms=["HS256"], issuer=None, audience=None
    )
    store = TokenService(settings).store
    authenticator = JWTAuthenticator(settings, revocation_store=store)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/protected")
    async def protected(payload=Depends(require_scopes("read"))) -> dict[str, object]:
        return payload

    token = make_token(["read"], ["user"])
    service = TokenService(settings, store=store)
    service.revoke(token)

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
