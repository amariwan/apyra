from __future__ import annotations

import ssl
from email.message import EmailMessage as SMTPMessage
from threading import get_ident
from typing import Self, cast

import pytest
from pydantic import SecretStr

from apyra.email import (
    ConsoleEmailBackend,
    EmailBackendName,
    EmailDispatcher,
    EmailMessage,
    EmailSettings,
)
from apyra.email.backends import SMTPEmailBackend


@pytest.mark.asyncio
async def test_console_backend_captures_message() -> None:
    backend = ConsoleEmailBackend()
    dispatcher = EmailDispatcher(backend)
    message = EmailMessage(subject="hi", recipients=("a@example.com",), text="hello")
    await dispatcher.send(message)
    assert backend.sent == [message]


@pytest.mark.asyncio
async def test_email_dispatcher_propagates_enqueue_errors_when_fallback_is_disabled() -> None:
    class Backend:
        def __init__(self) -> None:
            self.sent: list[EmailMessage] = []

        async def send(self, message: EmailMessage) -> None:
            self.sent.append(message)

    class Queue:
        def __init__(self) -> None:
            self.accepted: list[EmailMessage] = []

        async def enqueue(self, message: EmailMessage) -> None:
            self.accepted.append(message)
            raise RuntimeError("queue acknowledgement lost")

        async def close(self) -> None:
            pass

    backend = Backend()
    queue = Queue()
    dispatcher = EmailDispatcher(backend, queue, fallback_on_enqueue_error=False)
    message = EmailMessage(subject="hello", recipients=("a@example.com",), text="body")

    with pytest.raises(RuntimeError, match="queue acknowledgement lost"):
        await dispatcher.send(message)

    assert backend.sent == []
    assert queue.accepted == [message]


def test_email_message_headers_are_immutable_snapshots() -> None:
    headers = {"X-Trace": "original"}
    message = EmailMessage(
        subject="hi", recipients=("a@example.com",), text="hello", headers=headers
    )

    headers["X-Trace"] = "mutated"
    assert message.headers["X-Trace"] == "original"
    with pytest.raises(TypeError):
        cast(dict[str, str], message.headers)["X-Trace"] = "changed"


def test_email_message_payload_round_trip_and_defaults() -> None:
    message = EmailMessage(
        subject="hello",
        recipients=("a@example.com", "b@example.com"),
        text="plain body",
        html="<p>body</p>",
        reply_to="reply@example.com",
        headers={"X-Trace": "trace-1"},
    )

    assert EmailMessage.from_payload(message.to_payload()) == message
    assert EmailMessage.from_payload({"subject": "hello", "text": "body"}) == EmailMessage(
        subject="hello", recipients=(), text="body"
    )


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"subject": "hello", "text": "body", "recipients": "a@example.com"}, "recipients"),
        ({"subject": "hello", "text": "body", "recipients": [1]}, "recipients"),
        ({"subject": "hello", "text": "body", "headers": []}, "headers"),
        ({"subject": "hello", "text": "body", "headers": {"X": 1}}, "headers"),
        ({"subject": 1, "text": "body"}, "subject and text"),
        ({"subject": "hello", "text": 1}, "subject and text"),
        ({"subject": "hello", "text": "body", "html": 1}, "html"),
        ({"subject": "hello", "text": "body", "reply_to": 1}, "reply_to"),
    ],
)
def test_email_message_from_payload_rejects_invalid_fields(
    payload: dict[str, object], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        EmailMessage.from_payload(payload)


def test_smtp_ssl_uses_certificate_verifying_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class SMTPClient:
        def __init__(
            self, host: str, port: int, *, timeout: float, context: ssl.SSLContext
        ) -> None:
            captured.update(host=host, port=port, timeout=timeout, context=context)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def send_message(
            self, _message: object, *, to_addrs: tuple[str, ...] | None = None
        ) -> None:
            captured["to_addrs"] = to_addrs

    monkeypatch.setattr("apyra.email.backends.smtplib.SMTP_SSL", SMTPClient)
    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.SMTP,
        EMAIL_SMTP_HOST="mail.example",
        EMAIL_SMTP_SSL=True,
    )

    SMTPEmailBackend(settings)._send_sync(
        EmailMessage(
            subject="hello",
            recipients=("recipient@example.com",),
            text="body",
            headers={"Bcc": "hidden@example.com"},
        )
    )

    context = captured["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert captured["to_addrs"] == ("recipient@example.com",)


@pytest.mark.asyncio
async def test_smtp_send_uses_starttls_and_offloads_blocking_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class SMTPClient:
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            captured.update(host=host, port=port, timeout=timeout, thread_id=get_ident())

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def starttls(self, *, context: ssl.SSLContext) -> None:
            captured["starttls_context"] = context

        def login(self, username: str, password: str) -> None:
            captured["credentials"] = (username, password)

        def send_message(
            self, message: SMTPMessage, *, to_addrs: tuple[str, ...] | None = None
        ) -> None:
            captured["message"] = message
            captured["to_addrs"] = to_addrs

    monkeypatch.setattr("apyra.email.backends.smtplib.SMTP", SMTPClient)
    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.SMTP,
        EMAIL_SMTP_HOST="mail.example",
        EMAIL_SMTP_USERNAME="mailer",
        EMAIL_SMTP_PASSWORD=SecretStr("smtp-password"),
        EMAIL_SMTP_STARTTLS=True,
        EMAIL_FROM="from@example.com",
    )
    main_thread_id = get_ident()
    message = EmailMessage(
        subject="hello",
        recipients=("recipient@example.com",),
        text="plain body",
        html="<p>body</p>",
        reply_to="reply@example.com",
    )

    await SMTPEmailBackend(settings).send(message)

    tls_context = cast(ssl.SSLContext, captured["starttls_context"])
    smtp_message = cast(SMTPMessage, captured["message"])
    assert captured["thread_id"] != main_thread_id
    assert tls_context.verify_mode == ssl.CERT_REQUIRED
    assert tls_context.check_hostname
    assert captured["credentials"] == ("mailer", "smtp-password")
    assert captured["to_addrs"] == message.recipients
    assert smtp_message["Reply-To"] == "reply@example.com"
    assert smtp_message.is_multipart()
