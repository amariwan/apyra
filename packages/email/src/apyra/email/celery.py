"""Celery worker registration for email messages."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from apyra.email.backends import EmailBackend
from apyra.email.factory import build_email_backend
from apyra.email.models import EmailMessage
from apyra.email.settings import get_email_settings

EmailTask = Callable[..., None]


class CeleryTaskRegistrar(Protocol):
    """Minimal Celery application contract needed to register the email task."""

    def task(self, *, name: str) -> Callable[[EmailTask], EmailTask]:
        """Register and return a task under the supplied name."""
        ...


def register_celery_email_task(
    celery_app: CeleryTaskRegistrar,
    *,
    backend: EmailBackend | None = None,
) -> EmailTask:
    """Register the configured synchronous worker task and return it for inspection."""

    direct_backend = backend if backend is not None else build_email_backend()
    task_name = get_email_settings().EMAIL_CELERY_TASK_NAME

    def deliver_email(*, message: dict[str, object]) -> None:
        asyncio.run(direct_backend.send(EmailMessage.from_payload(message)))

    return celery_app.task(name=task_name)(deliver_email)


__all__ = ["CeleryTaskRegistrar", "register_celery_email_task"]
