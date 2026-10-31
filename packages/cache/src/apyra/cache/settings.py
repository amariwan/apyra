"""Cache backend settings."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheBackend(StrEnum):
    """Supported cache backend identifiers."""

    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class CacheSettings(BaseSettings):
    """Cache backend and expiration settings loaded from environment files."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(".env", ".env.local"), case_sensitive=False, extra="ignore"
    )

    cache_enabled: bool = True
    cache_backend: CacheBackend = CacheBackend.MEMORY
    cache_default_ttl_seconds: int = Field(default=300, ge=1)
    cache_max_entries: int = Field(default=1024, ge=1)
    cache_key_prefix: str = "app"
    cache_redis_url: str | None = Field(default=None, repr=False)
    cache_memcached_servers: str | None = None
    cache_memcached_allow_server_flush: bool = False

    @model_validator(mode="after")
    def validate_redis(self) -> CacheSettings:
        """Require connection settings when an external backend is enabled."""
        if not self.cache_enabled:
            return self
        if self.cache_backend is CacheBackend.REDIS and not self.cache_redis_url:
            raise ValueError("CACHE_REDIS_URL is required for the Redis cache backend")
        if self.cache_backend is CacheBackend.MEMCACHED and not self.cache_memcached_servers:
            raise ValueError("CACHE_MEMCACHED_SERVERS is required for the Memcached cache backend")
        return self

    @property
    def enabled(self) -> bool:
        """Return whether cache operations use the configured backend."""
        return self.cache_enabled


def _alias(field_name: str) -> property:
    def getter(self: CacheSettings) -> object:
        return getattr(self, field_name)

    return property(getter)


for _field in CacheSettings.model_fields:
    setattr(CacheSettings, _field.upper(), _alias(_field))


@lru_cache(maxsize=1)
def get_cache_settings() -> CacheSettings:
    """Return the cached cache settings instance."""
    return CacheSettings()
