"""Email delivery settings."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailBackendName(StrEnum):
    """Supported backend names selected by ``EMAIL_BACKEND``."""

    CONSOLE = "console"
    SMTP = "smtp"
    SES = "ses"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    POSTMARK = "postmark"
    BREVO = "brevo"


class EmailSettings(BaseSettings):
    """Environment-backed provider, queue, and delivery settings."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(".env", ".env.dev"), case_sensitive=False, extra="ignore"
    )

    EMAIL_ENABLED: bool = True
    EMAIL_BACKEND: EmailBackendName = EmailBackendName.CONSOLE
    EMAIL_FROM: str = "noreply@localhost"
    EMAIL_SMTP_HOST: str | None = None
    EMAIL_SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    EMAIL_SMTP_USERNAME: str | None = None
    EMAIL_SMTP_PASSWORD: SecretStr | None = None
    EMAIL_SMTP_STARTTLS: bool = True
    EMAIL_SMTP_SSL: bool = False
    EMAIL_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    EMAIL_SENDGRID_API_KEY: str | None = Field(default=None, repr=False)
    EMAIL_MAILGUN_API_KEY: str | None = Field(default=None, repr=False)
    EMAIL_MAILGUN_DOMAIN: str | None = None
    EMAIL_POSTMARK_SERVER_TOKEN: str | None = Field(default=None, repr=False)
    EMAIL_BREVO_API_KEY: str | None = Field(default=None, repr=False)
    EMAIL_SES_REGION: str = "us-east-1"
    EMAIL_USE_CELERY: bool = False
    EMAIL_QUEUE_FALLBACK_TO_DIRECT: bool = True
    EMAIL_CELERY_BROKER_URL: str | None = Field(default=None, repr=False)
    EMAIL_CELERY_TASK_NAME: str = "app.core.email.send"

    @property
    def ENABLED(self) -> bool:
        """Return the legacy uppercase alias for ``EMAIL_ENABLED``."""
        return self.EMAIL_ENABLED

    @property
    def enabled(self) -> bool:
        """Return the lowercase alias for ``EMAIL_ENABLED``."""
        return self.EMAIL_ENABLED

    @model_validator(mode="after")
    def validate_selected_backends(self) -> EmailSettings:
        """Validate required provider settings when delivery is enabled."""
        if not self.EMAIL_ENABLED:
            return self
        if self.EMAIL_BACKEND is EmailBackendName.SMTP and not self.EMAIL_SMTP_HOST:
            raise ValueError("EMAIL_SMTP_HOST is required for the SMTP backend")
        if self.EMAIL_BACKEND is EmailBackendName.SENDGRID and not self.EMAIL_SENDGRID_API_KEY:
            raise ValueError("EMAIL_SENDGRID_API_KEY is required for the SendGrid backend")
        if self.EMAIL_BACKEND is EmailBackendName.MAILGUN and not (
            self.EMAIL_MAILGUN_API_KEY and self.EMAIL_MAILGUN_DOMAIN
        ):
            raise ValueError(
                "EMAIL_MAILGUN_API_KEY and EMAIL_MAILGUN_DOMAIN are required for the Mailgun backend"
            )
        if self.EMAIL_BACKEND is EmailBackendName.POSTMARK and not self.EMAIL_POSTMARK_SERVER_TOKEN:
            raise ValueError("EMAIL_POSTMARK_SERVER_TOKEN is required for the Postmark backend")
        if self.EMAIL_BACKEND is EmailBackendName.BREVO and not self.EMAIL_BREVO_API_KEY:
            raise ValueError("EMAIL_BREVO_API_KEY is required for the Brevo backend")
        if self.EMAIL_USE_CELERY and not self.EMAIL_CELERY_BROKER_URL:
            raise ValueError("EMAIL_CELERY_BROKER_URL is required when EMAIL_USE_CELERY=true")
        return self


@lru_cache(maxsize=1)
def get_email_settings() -> EmailSettings:
    """Return the process-cached email settings."""

    return EmailSettings()


__all__ = ["EmailBackendName", "EmailSettings", "get_email_settings"]
