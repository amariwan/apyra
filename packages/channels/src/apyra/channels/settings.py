"""Optional channel-layer settings."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelBackend(StrEnum):
    """Supported channel-layer implementations."""

    MEMORY = "memory"
    REDIS = "redis"


class ChannelSettings(BaseSettings):
    """Configuration for optional in-process or Redis channel layers."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(".env", ".env.dev"), case_sensitive=False, extra="ignore"
    )

    CHANNELS_ENABLED: bool = False
    CHANNELS_BACKEND: ChannelBackend = ChannelBackend.MEMORY
    CHANNELS_REDIS_URL: str | None = Field(default=None, repr=False)
    CHANNELS_PREFIX: str = "app:channels"
    CHANNELS_QUEUE_SIZE: int = Field(default=100, ge=1)

    @property
    def ENABLED(self) -> bool:
        return self.CHANNELS_ENABLED

    @property
    def enabled(self) -> bool:
        return self.CHANNELS_ENABLED

    @model_validator(mode="after")
    def validate_redis(self) -> ChannelSettings:
        if (
            self.CHANNELS_ENABLED
            and self.CHANNELS_BACKEND is ChannelBackend.REDIS
            and not self.CHANNELS_REDIS_URL
        ):
            raise ValueError("CHANNELS_REDIS_URL is required for the Redis channel backend")
        return self


@lru_cache(maxsize=1)
def get_channel_settings() -> ChannelSettings:
    return ChannelSettings()


__all__ = ["ChannelBackend", "ChannelSettings", "get_channel_settings"]
