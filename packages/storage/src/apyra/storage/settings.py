"""Storage configuration via environment variables."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from typing import ClassVar, cast

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageBackend(StrEnum):
    """Supported storage backends."""

    FILESYSTEM = "filesystem"
    S3 = "s3"


class StorageSettings(BaseSettings):
    """S3-compatible storage configuration."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        case_sensitive=False,
        extra="ignore",
    )

    storage_enabled: bool = True
    storage_backend: StorageBackend = StorageBackend.FILESYSTEM

    s3_endpoint: str | None = Field(default=None, repr=False)
    s3_access_key_id: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("accessKey", "S3_ACCESS_KEY_ID", "s3_access_key_id"),
    )
    s3_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("secretKey", "S3_SECRET_ACCESS_KEY", "s3_secret_access_key"),
    )
    s3_bucket: str = ""
    s3_region: str | None = None
    s3_secure: bool = True
    s3_addressing_style: str = "auto"
    s3_prefix: str = ""

    filesystem_root: str = "data"

    @property
    def enabled(self) -> bool:
        return self.storage_enabled

    @model_validator(mode="before")
    @classmethod
    def _normalize_s3_credential_aliases(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        mapping = cast(Mapping[object, object], data)
        normalized: dict[str, object] = {str(key): value for key, value in mapping.items()}
        lowered = {str(key).lower(): value for key, value in normalized.items()}

        if normalized.get("s3_access_key_id") in (None, ""):
            access_key = lowered.get("s3_access_key_id") or lowered.get("accesskey")
            if access_key not in (None, ""):
                normalized["s3_access_key_id"] = access_key

        if normalized.get("s3_secret_access_key") in (None, ""):
            secret_key = lowered.get("s3_secret_access_key") or lowered.get("secretkey")
            if secret_key not in (None, ""):
                normalized["s3_secret_access_key"] = secret_key

        return normalized


def _alias(field_name: str) -> property:
    def getter(self: StorageSettings) -> object:
        return getattr(self, field_name)

    return property(getter)


for _field in StorageSettings.model_fields:
    setattr(StorageSettings, _field.upper(), _alias(_field))


@lru_cache(maxsize=1)
def get_storage_settings() -> StorageSettings:
    """Return a cached singleton StorageSettings instance."""
    return StorageSettings()
