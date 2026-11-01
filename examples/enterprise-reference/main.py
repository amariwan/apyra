"""Application entry point for the Apyra Enterprise Reference."""

from __future__ import annotations

import os

from apyra.auth import AuthSettings, JWTAuthenticator, TokenService
from apyra.core import Settings
from apyra.db import Base
from apyra.fastapi import create_app
from apyra.observability import (
    configure_logging,
    configure_opentelemetry,
    instrument_fastapi,
    instrument_sqlalchemy,
)
from apyra.workflow.models import WorkflowRecord  # noqa: F401  (register table)
from pydantic import SecretStr

from api.router import router as api_router
from api.router import session_manager
from infrastructure.models import OrderModel  # noqa: F401

configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), json_output=True)

try:
    configure_opentelemetry(
        service_name=os.getenv("OTEL_SERVICE_NAME", "apyra-enterprise-reference"),
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    _otel_enabled = True
except RuntimeError:
    _otel_enabled = False

_JWT_SECRET = os.getenv(
    "APYRA_REFERENCE_JWT_SECRET", "dev-only-reference-secret-change-me-please-32chars"
)
auth_settings = AuthSettings(
    mode="hs",
    hs_secret=SecretStr(_JWT_SECRET),
    algorithms=["HS256"],
    issuer="apyra-reference",
    audience="apyra-reference-api",
    expected_access_token_type="access",
)
token_service = TokenService(auth_settings)
authenticator = JWTAuthenticator(auth_settings, revocation_store=token_service.store)


async def _startup(app: object) -> None:
    engine = session_manager.engine
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    instrument_sqlalchemy(engine)
    instrument_fastapi(app)
    app.state.authenticator = authenticator  # type: ignore[attr-defined]
    app.state.auth_settings = auth_settings  # type: ignore[attr-defined]
    app.state.token_service = token_service  # type: ignore[attr-defined]
    app.state.revocation_store = token_service.store  # type: ignore[attr-defined]


async def _shutdown(app: object) -> None:
    await session_manager.close()


app = create_app(
    title="Apyra Enterprise Reference",
    routers=[api_router],
    settings=Settings(api_prefix="/api"),
    startup=[_startup],
    shutdown=[_shutdown],
)
