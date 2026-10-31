from __future__ import annotations

from types import ModuleType
from typing import Any

import pytest

from apyra.email import EmailBackendName, EmailDeliveryMode, EmailMessage, EmailSettings, factory
from apyra.email.backends import (
    BrevoEmailBackend,
    ConsoleEmailBackend,
    MailgunEmailBackend,
    PostmarkEmailBackend,
    SendGridEmailBackend,
    SESEmailBackend,
    SMTPEmailBackend,
)
from apyra.email.dispatcher import CeleryEmailQueue


class FakeCeleryApp:
    def __init__(self) -> None:
        self.task_name: str | None = None
        self.task_kwargs: dict[str, object] | None = None
        self.closed = False

    def send_task(self, name: str, *, kwargs: dict[str, object]) -> object:
        self.task_name = name
        self.task_kwargs = kwargs
        return object()

    def close(self) -> None:
        self.closed = True


def _settings(**values: Any) -> EmailSettings:
    return EmailSettings(_env_file=None, _env_prefix="APYRA_EMAIL_FACTORY_TEST_", **values)  # pyright: ignore[reportCallIssue]


def test_email_settings_repr_redacts_credentials_without_changing_values() -> None:
    settings = _settings(
        EMAIL_SENDGRID_API_KEY="sendgrid-secret",
        EMAIL_POSTMARK_SERVER_TOKEN="postmark-secret",
        EMAIL_CELERY_BROKER_URL="amqps://user:broker-secret@broker.example/vhost",
    )

    representation = repr(settings)

    assert "sendgrid-secret" not in representation
    assert "postmark-secret" not in representation
    assert "broker-secret" not in representation
    assert settings.EMAIL_SENDGRID_API_KEY == "sendgrid-secret"
    assert settings.EMAIL_POSTMARK_SERVER_TOKEN == "postmark-secret"


def test_settings_helper_ignores_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "ambient.example")
    monkeypatch.setenv("EMAIL_USE_CELERY", "true")

    settings = _settings(EMAIL_BACKEND=EmailBackendName.CONSOLE, EMAIL_USE_CELERY=False)

    assert settings.EMAIL_BACKEND is EmailBackendName.CONSOLE
    assert settings.EMAIL_SMTP_HOST is None
    assert not settings.EMAIL_USE_CELERY


def test_disabled_email_does_not_require_backend_configuration() -> None:
    settings = _settings(
        EMAIL_ENABLED=False,
        EMAIL_BACKEND=EmailBackendName.SMTP,
        EMAIL_USE_CELERY=True,
    )

    assert not settings.EMAIL_ENABLED


@pytest.mark.asyncio
async def test_disabled_email_does_not_initialize_or_use_delivery_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(EMAIL_ENABLED=False)
    factory.get_email_dispatcher.cache_clear()
    monkeypatch.setattr(factory, "get_email_settings", lambda: settings)
    monkeypatch.setattr(
        factory, "build_email_backend", lambda: pytest.fail("backend must not be initialized")
    )
    monkeypatch.setattr(
        factory, "_build_queue", lambda: pytest.fail("queue must not be initialized")
    )

    try:
        dispatcher = factory.get_email_dispatcher()
        result = await dispatcher.send(
            EmailMessage(subject="hello", recipients=("a@example.com",), text="body")
        )
    finally:
        factory.get_email_dispatcher.cache_clear()

    assert result is EmailDeliveryMode.DISABLED


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_to_direct", [False, True, None])
async def test_email_factory_applies_queue_failure_fallback_setting(
    monkeypatch: pytest.MonkeyPatch,
    fallback_to_direct: bool | None,
) -> None:
    class Backend:
        def __init__(self) -> None:
            self.sent: list[EmailMessage] = []

        async def send(self, message: EmailMessage) -> None:
            self.sent.append(message)

    class AcceptedThenFailedQueue:
        def __init__(self) -> None:
            self.accepted: list[EmailMessage] = []

        async def enqueue(self, message: EmailMessage) -> None:
            self.accepted.append(message)
            raise RuntimeError("queue acknowledgement lost")

        async def close(self) -> None:
            pass

    settings = (
        _settings()
        if fallback_to_direct is None
        else _settings(EMAIL_QUEUE_FALLBACK_TO_DIRECT=fallback_to_direct)
    )
    backend = Backend()
    queue = AcceptedThenFailedQueue()
    factory.get_email_dispatcher.cache_clear()
    monkeypatch.setattr(factory, "get_email_settings", lambda: settings)
    monkeypatch.setattr(factory, "build_email_backend", lambda: backend)
    monkeypatch.setattr(factory, "_build_queue", lambda: queue)
    message = EmailMessage(subject="hello", recipients=("a@example.com",), text="body")

    try:
        dispatcher = factory.get_email_dispatcher()
        if fallback_to_direct is not False:
            result = await dispatcher.send(message)
            assert result is EmailDeliveryMode.DIRECT_FALLBACK
            assert backend.sent == [message]
        else:
            with pytest.raises(RuntimeError, match="queue acknowledgement lost"):
                await dispatcher.send(message)
            assert backend.sent == []
    finally:
        factory.get_email_dispatcher.cache_clear()

    assert queue.accepted == [message]


@pytest.mark.parametrize(
    ("settings", "expected_type"),
    [
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.CONSOLE,
                EMAIL_USE_CELERY=False,
            ),
            ConsoleEmailBackend,
        ),
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.SMTP,
                EMAIL_SMTP_HOST="smtp.example",
            ),
            SMTPEmailBackend,
        ),
        (_settings(EMAIL_BACKEND=EmailBackendName.SES), SESEmailBackend),
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.SENDGRID,
                EMAIL_SENDGRID_API_KEY="sendgrid-key",
            ),
            SendGridEmailBackend,
        ),
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.MAILGUN,
                EMAIL_MAILGUN_API_KEY="mailgun-key",
                EMAIL_MAILGUN_DOMAIN="example.com",
            ),
            MailgunEmailBackend,
        ),
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.POSTMARK,
                EMAIL_POSTMARK_SERVER_TOKEN="postmark-token",
            ),
            PostmarkEmailBackend,
        ),
        (
            _settings(
                EMAIL_BACKEND=EmailBackendName.BREVO,
                EMAIL_BREVO_API_KEY="brevo-key",
            ),
            BrevoEmailBackend,
        ),
    ],
)
def test_build_email_backend_selects_configured_backend(
    monkeypatch: pytest.MonkeyPatch, settings: EmailSettings, expected_type: type[object]
) -> None:
    monkeypatch.setattr(factory, "get_email_settings", lambda: settings)

    assert isinstance(factory.build_email_backend(), expected_type)


def test_build_queue_is_disabled_without_celery_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        factory,
        "get_email_settings",
        lambda: _settings(
            EMAIL_BACKEND=EmailBackendName.CONSOLE,
            EMAIL_USE_CELERY=False,
        ),
    )

    assert factory._build_queue() is None


def test_build_queue_fails_when_celery_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        EMAIL_BACKEND=EmailBackendName.CONSOLE,
        EMAIL_USE_CELERY=True,
        EMAIL_CELERY_BROKER_URL="memory://",
    )
    monkeypatch.setattr(factory, "get_email_settings", lambda: settings)

    def unavailable_celery(_name: str) -> ModuleType:
        raise ImportError("celery unavailable")

    monkeypatch.setattr(
        factory,
        "import_module",
        unavailable_celery,
    )

    with pytest.raises(RuntimeError, match="EMAIL_USE_CELERY requires the 'celery' project extra"):
        factory._build_queue()


@pytest.mark.asyncio
async def test_build_queue_uses_celery_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        EMAIL_BACKEND=EmailBackendName.CONSOLE,
        EMAIL_USE_CELERY=True,
        EMAIL_CELERY_BROKER_URL="memory://",
        EMAIL_CELERY_TASK_NAME="mail.send",
    )
    celery_app = FakeCeleryApp()
    celery_module = ModuleType("celery.app.base")
    celery_module.Celery = lambda _name, *, broker: celery_app  # type: ignore[attr-defined]
    monkeypatch.setattr(factory, "get_email_settings", lambda: settings)

    def import_celery(_name: str) -> ModuleType:
        return celery_module

    monkeypatch.setattr(factory, "import_module", import_celery)

    queue = factory._build_queue()
    assert isinstance(queue, CeleryEmailQueue)
    message = EmailMessage(subject="hi", recipients=("a@example.com",), text="hello")
    await queue.enqueue(message)

    assert celery_app.task_name == "mail.send"
    assert celery_app.task_kwargs == {"message": message.to_payload()}
    await queue.close()
    assert celery_app.closed


@pytest.mark.asyncio
async def test_close_email_dispatcher_does_not_construct_when_uninitialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory.get_email_dispatcher.cache_clear()
    monkeypatch.setattr(
        factory,
        "build_email_backend",
        lambda: (_ for _ in ()).throw(AssertionError("dispatcher should not be created")),
    )

    await factory.close_email_dispatcher()


@pytest.mark.asyncio
async def test_close_email_dispatcher_closes_cached_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class Backend:
        async def send(self, _message: EmailMessage) -> None:
            pass

    class Queue:
        def __init__(self) -> None:
            self.closed = False

        async def enqueue(self, _message: EmailMessage) -> None:
            pass

        async def close(self) -> None:
            self.closed = True

    queue = Queue()
    monkeypatch.setattr(factory, "build_email_backend", Backend)
    monkeypatch.setattr(factory, "_build_queue", lambda: queue)
    factory.get_email_dispatcher.cache_clear()
    try:
        factory.get_email_dispatcher()
        await factory.close_email_dispatcher()
        assert queue.closed
        assert factory.get_email_dispatcher.cache_info().currsize == 0
    finally:
        factory.get_email_dispatcher.cache_clear()
