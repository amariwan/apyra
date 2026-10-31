"""Direct email delivery backends."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage as SMTPMessage
from typing import Any, Protocol, cast

from apyra.email.models import EmailMessage
from apyra.email.settings import EmailSettings

logger: logging.Logger = logging.getLogger("app_logger")


class EmailBackend(Protocol):
    """Async contract implemented by email delivery backends."""

    async def send(self, message: EmailMessage) -> None:
        """Deliver one message or raise when the provider rejects it."""
        ...


class ConsoleEmailBackend:
    """Safe development backend that logs metadata without message contents."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        """Record the message and log metadata without exposing its contents."""
        self.sent.append(message)
        logger.info(
            "Email accepted by console backend: subject=%r recipients=%s",
            message.subject,
            len(message.recipients),
        )


class SMTPEmailBackend:
    """Deliver messages through SMTP, STARTTLS, or implicit TLS."""

    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        """Send the message using SMTP without blocking the event loop."""
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        settings = self._settings
        host = settings.EMAIL_SMTP_HOST
        if host is None:
            raise RuntimeError("SMTP host is not configured")
        smtp_message = SMTPMessage()
        smtp_message["Subject"] = message.subject
        smtp_message["From"] = settings.EMAIL_FROM
        smtp_message["To"] = ", ".join(message.recipients)
        if message.reply_to:
            smtp_message["Reply-To"] = message.reply_to
        for name, value in message.headers.items():
            smtp_message[name] = value
        smtp_message.set_content(message.text)
        if message.html:
            smtp_message.add_alternative(message.html, subtype="html")

        smtp_client: smtplib.SMTP | smtplib.SMTP_SSL
        if settings.EMAIL_SMTP_SSL:
            smtp_client = smtplib.SMTP_SSL(
                host,
                settings.EMAIL_SMTP_PORT,
                timeout=settings.EMAIL_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            )
        else:
            smtp_client = smtplib.SMTP(
                host,
                settings.EMAIL_SMTP_PORT,
                timeout=settings.EMAIL_TIMEOUT_SECONDS,
            )

        with smtp_client as client:
            if settings.EMAIL_SMTP_STARTTLS and not settings.EMAIL_SMTP_SSL:
                client.starttls(context=ssl.create_default_context())
            if settings.EMAIL_SMTP_USERNAME:
                password = (
                    settings.EMAIL_SMTP_PASSWORD.get_secret_value()
                    if settings.EMAIL_SMTP_PASSWORD
                    else ""
                )
                client.login(settings.EMAIL_SMTP_USERNAME, password)
            # Keep SMTP envelope recipients authoritative; arbitrary Cc/Bcc
            # headers must not expand the set of recipients from the payload.
            client.send_message(smtp_message, to_addrs=message.recipients)


__all__ = ["ConsoleEmailBackend", "EmailBackend", "SMTPEmailBackend"]


class _HttpBackend:
    """Shared timeout and client construction for HTTP provider adapters."""

    def __init__(self, timeout_seconds: float = 10.0, transport: object | None = None) -> None:
        self._timeout = timeout_seconds
        self._transport = transport

    def _client(self) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("HTTP email providers require the 'httpx' project extra") from exc
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)  # type: ignore[arg-type]


class SendGridEmailBackend(_HttpBackend):
    """Deliver messages through SendGrid's HTTP API using the ``providers`` extra."""

    def __init__(self, settings: EmailSettings, *, transport: object | None = None) -> None:
        super().__init__(settings.EMAIL_TIMEOUT_SECONDS, transport)
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        """Send one message through the SendGrid HTTP API."""

        api_key = self._settings.EMAIL_SENDGRID_API_KEY
        if not api_key:
            raise RuntimeError("SendGrid API key is not configured")
        content = [{"type": "text/plain", "value": message.text}]
        if message.html:
            content.append({"type": "text/html", "value": message.html})
        payload = {
            "personalizations": [
                {"to": [{"email": recipient} for recipient in message.recipients]}
            ],
            "from": {"email": self._settings.EMAIL_FROM},
            "subject": message.subject,
            "content": content,
        }
        if message.reply_to:
            payload["reply_to"] = {"email": message.reply_to}
        async with self._client() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()


class MailgunEmailBackend(_HttpBackend):
    """Deliver messages through Mailgun's HTTP API using the ``providers`` extra."""

    def __init__(self, settings: EmailSettings, *, transport: object | None = None) -> None:
        super().__init__(settings.EMAIL_TIMEOUT_SECONDS, transport)
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        """Send one message through the Mailgun HTTP API."""

        api_key = self._settings.EMAIL_MAILGUN_API_KEY
        domain = self._settings.EMAIL_MAILGUN_DOMAIN
        if not api_key or not domain:
            raise RuntimeError("Mailgun credentials are not configured")
        data = {
            "from": self._settings.EMAIL_FROM,
            "to": list(message.recipients),
            "subject": message.subject,
            "text": message.text,
        }
        if message.html:
            data["html"] = message.html
        if message.reply_to:
            data["h:Reply-To"] = message.reply_to
        async with self._client() as client:
            response = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=(api_key, ""),
                data=data,
            )
            response.raise_for_status()


class PostmarkEmailBackend(_HttpBackend):
    """Deliver messages through Postmark's HTTP API using the ``providers`` extra."""

    def __init__(self, settings: EmailSettings, *, transport: object | None = None) -> None:
        super().__init__(settings.EMAIL_TIMEOUT_SECONDS, transport)
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        """Send one message through the Postmark HTTP API."""

        token = self._settings.EMAIL_POSTMARK_SERVER_TOKEN
        if not token:
            raise RuntimeError("Postmark server token is not configured")
        payload = {
            "From": self._settings.EMAIL_FROM,
            "To": ", ".join(message.recipients),
            "Subject": message.subject,
            "TextBody": message.text,
        }
        if message.html:
            payload["HtmlBody"] = message.html
        if message.reply_to:
            payload["ReplyTo"] = message.reply_to
        async with self._client() as client:
            response = await client.post(
                "https://api.postmarkapp.com/email",
                headers={"X-Postmark-Server-Token": token},
                json=payload,
            )
            response.raise_for_status()


class BrevoEmailBackend(_HttpBackend):
    """Deliver messages through Brevo's HTTP API using the ``providers`` extra."""

    def __init__(self, settings: EmailSettings, *, transport: object | None = None) -> None:
        super().__init__(settings.EMAIL_TIMEOUT_SECONDS, transport)
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        """Send one message through the Brevo HTTP API."""

        api_key = self._settings.EMAIL_BREVO_API_KEY
        if not api_key:
            raise RuntimeError("Brevo API key is not configured")
        payload = {
            "sender": {"email": self._settings.EMAIL_FROM},
            "to": [{"email": recipient} for recipient in message.recipients],
            "subject": message.subject,
            "textContent": message.text,
        }
        if message.html:
            payload["htmlContent"] = message.html
        if message.reply_to:
            payload["replyTo"] = {"email": message.reply_to}
        async with self._client() as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": api_key},
                json=payload,
            )
            response.raise_for_status()


class SESEmailBackend:
    """Deliver messages through Amazon SES using the ``providers`` extra."""

    def __init__(self, settings: EmailSettings, *, client: object | None = None) -> None:
        self._settings = settings
        self._client: Any = client

    async def send(self, message: EmailMessage) -> None:
        """Send one message through Amazon SES."""
        import asyncio

        client = self._client
        if client is None:
            try:
                import boto3  # pyright: ignore[reportMissingTypeStubs]
            except ModuleNotFoundError as exc:
                if exc.name != "boto3":
                    raise
                raise RuntimeError("SES backend requires boto3") from exc
            boto3_api: Any = cast(Any, boto3)
            client = boto3_api.client("ses", region_name=self._settings.EMAIL_SES_REGION)
            self._client = client

        def _send() -> None:
            body: dict[str, object] = {"Text": {"Data": message.text}}
            if message.html:
                body["Html"] = {"Data": message.html}
            client.send_email(
                Source=self._settings.EMAIL_FROM,
                Destination={"ToAddresses": list(message.recipients)},
                Message={"Subject": {"Data": message.subject}, "Body": body},
                **({"ReplyToAddresses": [message.reply_to]} if message.reply_to else {}),
            )

        await asyncio.to_thread(_send)


__all__ = [
    "BrevoEmailBackend",
    "ConsoleEmailBackend",
    "EmailBackend",
    "MailgunEmailBackend",
    "PostmarkEmailBackend",
    "SESEmailBackend",
    "SMTPEmailBackend",
    "SendGridEmailBackend",
]
