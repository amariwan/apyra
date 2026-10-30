"""Lazy email dispatcher factory."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Protocol, cast

from apyra.email.backends import (
    BrevoEmailBackend,
    ConsoleEmailBackend,
    EmailBackend,
    MailgunEmailBackend,
    PostmarkEmailBackend,
    SendGridEmailBackend,
    SESEmailBackend,
    SMTPEmailBackend,
)
from apyra.email.dispatcher import CeleryClient, CeleryEmailQueue, EmailDispatcher, EmailQueue
from apyra.email.settings import EmailBackendName, get_email_settings


class _CeleryFactory(Protocol):
    def __call__(self, name: str, *, broker: str | None) -> CeleryClient: ...


def build_email_backend() -> EmailBackend:
    settings = get_email_settings()
    if settings.EMAIL_BACKEND is EmailBackendName.SMTP:
        return SMTPEmailBackend(settings)
    if settings.EMAIL_BACKEND is EmailBackendName.SES:
        return SESEmailBackend(settings)
    if settings.EMAIL_BACKEND is EmailBackendName.SENDGRID:
        return SendGridEmailBackend(settings)
    if settings.EMAIL_BACKEND is EmailBackendName.MAILGUN:
        return MailgunEmailBackend(settings)
    if settings.EMAIL_BACKEND is EmailBackendName.POSTMARK:
        return PostmarkEmailBackend(settings)
    if settings.EMAIL_BACKEND is EmailBackendName.BREVO:
        return BrevoEmailBackend(settings)
    return ConsoleEmailBackend()


def _build_queue() -> EmailQueue | None:
    settings = get_email_settings()
    if not settings.EMAIL_USE_CELERY:
        return None
    try:
        celery_factory = cast(_CeleryFactory, vars(import_module("celery.app.base"))["Celery"])
    except ImportError:
        return None
    celery_app = celery_factory("core_email", broker=settings.EMAIL_CELERY_BROKER_URL)
    return CeleryEmailQueue(celery_app, settings.EMAIL_CELERY_TASK_NAME)


@lru_cache(maxsize=1)
def get_email_dispatcher() -> EmailDispatcher:
    return EmailDispatcher(build_email_backend(), _build_queue())


async def close_email_dispatcher() -> None:
    """Close the cached queue client if the dispatcher was initialized."""

    if get_email_dispatcher.cache_info().currsize == 0:
        return
    dispatcher = get_email_dispatcher()
    get_email_dispatcher.cache_clear()
    await dispatcher.close()


__all__ = ["build_email_backend", "close_email_dispatcher", "get_email_dispatcher"]
