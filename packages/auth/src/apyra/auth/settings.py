"""Authentication settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    mode: Literal["jwks", "hs"] = "jwks"
    verify_signature: bool = True
    verify_exp: bool = True
    verify_iss: bool = True
    verify_aud: bool = True
    clock_skew_secs: int = Field(default=60, ge=0, le=900)
    issuer: str | None = None
    audience: str | None = None
    access_token_cookie: str | None = "access_token"
    algorithms: list[str] | str = Field(default_factory=lambda: ["RS256"])
    jwks_url: HttpUrl | None = None
    oidc_discovery: bool = False
    oidc_discovery_url: HttpUrl | None = None
    oauth2_client_id: str | None = None
    oauth2_client_secret: SecretStr | None = None
    oauth2_introspection_url: HttpUrl | None = None
    hs_secret: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="AUTH_",
        case_sensitive=False,
        extra="ignore",
    )


def _alias(field_name: str) -> property:
    def getter(self: AuthSettings) -> object:
        return getattr(self, field_name)

    return property(getter)


for _field in AuthSettings.model_fields:
    setattr(AuthSettings, _field.upper(), _alias(_field))


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
