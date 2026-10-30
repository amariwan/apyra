"""Email delivery primitives for Apyra."""

from __future__ import annotations

from .backends import (
    BrevoEmailBackend,
    ConsoleEmailBackend,
    EmailBackend,
    MailgunEmailBackend,
    PostmarkEmailBackend,
    SendGridEmailBackend,
    SESEmailBackend,
    SMTPEmailBackend,
)
from .celery import CeleryTaskRegistrar, register_celery_email_task
from .dispatcher import CeleryEmailQueue, EmailDeliveryMode, EmailDispatcher, EmailQueue
from .factory import build_email_backend, close_email_dispatcher, get_email_dispatcher
from .models import EmailMessage
from .sdk_backends import (
    BrevoSDKEmailBackend,
    MailgunSDKEmailBackend,
    PostmarkSDKEmailBackend,
    SendGridSDKEmailBackend,
)
from .settings import EmailBackendName, EmailSettings, get_email_settings

__all__ = [
    "BrevoEmailBackend",
    "BrevoSDKEmailBackend",
    "CeleryEmailQueue",
    "CeleryTaskRegistrar",
    "ConsoleEmailBackend",
    "EmailBackend",
    "EmailBackendName",
    "EmailDeliveryMode",
    "EmailDispatcher",
    "EmailMessage",
    "EmailQueue",
    "EmailSettings",
    "MailgunEmailBackend",
    "MailgunSDKEmailBackend",
    "PostmarkEmailBackend",
    "PostmarkSDKEmailBackend",
    "SESEmailBackend",
    "SMTPEmailBackend",
    "SendGridEmailBackend",
    "SendGridSDKEmailBackend",
    "build_email_backend",
    "close_email_dispatcher",
    "get_email_dispatcher",
    "get_email_settings",
    "register_celery_email_task",
]
