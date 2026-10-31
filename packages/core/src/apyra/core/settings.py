"""Application settings for Apyra."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Small, explicit application settings.

    Settings are loaded from environment variables and optional ``.env`` files.
    They do not create network connections or other side effects.
    """

    app_name: str = "Apyra"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = ""
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = Field(default_factory=list)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="APYRA_",
        case_sensitive=False,
        extra="ignore",
    )

    def normalized_api_prefix(self) -> str:
        """Return the API prefix with one leading slash and no trailing slash."""
        prefix = self.api_prefix.strip()
        if not prefix:
            return ""
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/")
