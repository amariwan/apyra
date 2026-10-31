from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest

from apyra.email.celery import EmailTask, register_celery_email_task
from apyra.email.models import EmailMessage


class FalseyBackend:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def __bool__(self) -> bool:
        return False

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class FakeCeleryApp:
    def __init__(self) -> None:
        self.task_name: str | None = None

    def task(self, *, name: str) -> Callable[[EmailTask], EmailTask]:
        self.task_name = name
        return lambda task: task


def test_register_celery_email_task_uses_falsey_custom_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apyra.email import celery

    backend = FalseyBackend()
    app = FakeCeleryApp()
    message = EmailMessage(subject="hello", recipients=("a@example.com",), text="body")
    monkeypatch.setattr(
        celery, "build_email_backend", lambda: pytest.fail("backend should be used")
    )
    monkeypatch.setattr(
        celery,
        "get_email_settings",
        lambda: SimpleNamespace(EMAIL_CELERY_TASK_NAME="mail.send"),
    )

    task = register_celery_email_task(app, backend=backend)
    task(message=message.to_payload())

    assert app.task_name == "mail.send"
    assert backend.sent == [message]
