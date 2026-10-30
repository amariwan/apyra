"""Authenticated Apyra FastAPI application.

Demonstrates HS256 JWT issuance via ``TokenService`` and FastAPI auth
dependencies (``require_scopes`` / ``require_roles``).

Run with::

    uv run uvicorn main:app --app-dir examples/authenticated-api --reload

Try it::

    curl -s -X POST http://localhost:8000/api/login \\
      -H 'content-type: application/json' \\
      -d '{"username":"alice","password":"secret"}'
"""

from __future__ import annotations

from typing import Annotated

from apyra.auth import AuthSettings, JWTAuthenticator, TokenService
from apyra.core import Settings
from apyra.fastapi import create_app, require_roles, require_scopes
from pydantic import BaseModel, SecretStr

from fastapi import APIRouter, Depends, HTTPException

SECRET = "change-me-in-production-use-a-32-byte-secret-at-least"  # noqa: S105

auth_settings = AuthSettings(
    mode="hs",
    hs_secret=SecretStr(SECRET),
    algorithms=["HS256"],
)
token_service = TokenService(auth_settings)
authenticator = JWTAuthenticator(auth_settings, revocation_store=token_service.store)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    pair = token_service.issue_token_pair(body.username, scopes=["read"], access_expires_in=900)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.get("/me")
async def me(payload: Annotated[dict, Depends(require_scopes("read"))]) -> dict:
    return {"subject": payload.get("sub"), "scopes": payload.get("scopes", [])}


@router.get("/admin")
async def admin(payload: Annotated[dict, Depends(require_roles("admin"))]) -> dict:
    return {"subject": payload.get("sub")}


app = create_app(
    title="Authenticated Apyra API",
    routers=[router],
    settings=Settings(api_prefix="/api"),
)
app.state.authenticator = authenticator
app.state.auth_settings = auth_settings
app.state.revocation_store = token_service.store
