"""Authentication settings."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """JWT, JWKS, OIDC, and OAuth2 settings loaded from the environment."""

    mode: Literal["jwks", "hs"] = "jwks"
    verify_signature: bool = True
    verify_exp: bool = True
    verify_iss: bool = True
    verify_aud: bool = True
    clock_skew_secs: int = Field(default=60, ge=0, le=900)
    issuer: str | None = None
    audience: str | None = None
    expected_access_token_type: str | None = Field(
        default=None,
        min_length=1,
        description="Optional exact value required by the API access-token validator.",
    )
    expected_access_token_header_typ: str | None = Field(
        default=None,
        min_length=1,
        description="Optional exact JOSE typ header required by the API access-token validator.",
    )
    access_token_cookie: str | None = "access_token"
    algorithms: list[str] | str = Field(default_factory=lambda: ["RS256"])
    jwks_url: HttpUrl | None = Field(default=None, repr=False)
    oidc_discovery: bool = False
    oidc_discovery_url: HttpUrl | None = Field(default=None, repr=False)
    oauth2_client_id: str | None = None
    oauth2_client_secret: SecretStr | None = None
    oauth2_introspection_url: HttpUrl | None = Field(default=None, repr=False)
    hs_secret: SecretStr | None = None

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
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
    """Return the cached authentication settings instance."""
    return AuthSettings()
