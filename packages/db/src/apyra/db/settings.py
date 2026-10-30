"""Database configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseSettings):
    db_enabled: bool = Field(default=False, validation_alias="DB_ENABLED")
    db_backend: Literal["postgresql", "mysql", "sqlite"] = Field(
        default="postgresql", validation_alias="DB_BACKEND"
    )
    db_port: int | None = Field(default=None, validation_alias="DB_PORT")
    db_username: str | None = Field(default=None, validation_alias="DB_USERNAME")
    db_password: str | None = Field(default=None, validation_alias="DB_PASSWORD")
    db_database: str | None = Field(default=None, validation_alias="DB_DATABASE")
    db_ip: str = Field(default="localhost", validation_alias="DB_IP")
    db_engine_echo: bool = Field(default=False, validation_alias="DB_ENGINE_ECHO")
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, validation_alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(default=True, validation_alias="DB_POOL_PRE_PING")
    db_auto_create_tables: bool = Field(default=False, validation_alias="DB_AUTO_CREATE_TABLES")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def enabled(self) -> bool:
        return self.db_enabled

    @model_validator(mode="after")
    def _validate_required(self) -> DbSettings:
        if not self.db_enabled:
            return self
        required = (
            ("db_database",)
            if self.db_backend == "sqlite"
            else ("db_username", "db_password", "db_database")
        )
        missing = [name.upper() for name in required if getattr(self, name) in (None, "")]
        if missing:
            raise ValueError("DB is enabled but missing variables: " + ", ".join(missing))
        return self


@lru_cache(maxsize=1)
def get_db_settings() -> DbSettings:
    return DbSettings()


DatabaseSettings = DbSettings


def _alias(field_name: str) -> property:
    def getter(self: DbSettings) -> object:
        return getattr(self, field_name)

    return property(getter)


for _field in DbSettings.model_fields:
    setattr(DbSettings, _field.upper(), _alias(_field))
