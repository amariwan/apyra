"""Optional SDK-backed email delivery backends."""

from __future__ import annotations

import asyncio
from typing import Any

from apyra.email.models import EmailMessage
from apyra.email.settings import EmailSettings


class SendGridSDKEmailBackend:
    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import sendgrid  # pyright: ignore[reportMissingImports]
            from sendgrid.helpers.mail import Content, Email, Mail, To  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("SendGrid SDK backend requires the 'sendgrid' package") from exc

        api_key = self._settings.EMAIL_SENDGRID_API_KEY
        if not api_key:
            raise RuntimeError("SendGrid API key is not configured")
        mail = Mail(
            from_email=Email(self._settings.EMAIL_FROM),
            to_emails=[To(recipient) for recipient in message.recipients],
            subject=message.subject,
            plain_text_content=Content("text/plain", message.text),
        )
        if message.html:
            mail.add_content(Content("text/html", message.html))
        client = sendgrid.SendGridAPIClient(api_key)
        await asyncio.to_thread(client.send, mail)


class PostmarkSDKEmailBackend:
    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            from postmarker.core import PostmarkClient  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("Postmark SDK backend requires the 'postmarker' package") from exc

        token = self._settings.EMAIL_POSTMARK_SERVER_TOKEN
        if not token:
            raise RuntimeError("Postmark server token is not configured")
        client: Any = PostmarkClient(server_token=token)
        await asyncio.to_thread(
            client.emails.send,
            From=self._settings.EMAIL_FROM,
            To=", ".join(message.recipients),
            Subject=message.subject,
            TextBody=message.text,
            HtmlBody=message.html,
        )


class BrevoSDKEmailBackend:
    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import sib_api_v3_sdk  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("Brevo SDK backend requires the 'sib-api-v3-sdk' package") from exc

        api_key = self._settings.EMAIL_BREVO_API_KEY
        if not api_key:
            raise RuntimeError("Brevo API key is not configured")
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = api_key
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)
        email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"email": self._settings.EMAIL_FROM},
            to=[{"email": recipient} for recipient in message.recipients],
            subject=message.subject,
            text_content=message.text,
            html_content=message.html,
        )
        await asyncio.to_thread(api_instance.send_transac_email, email)


class MailgunSDKEmailBackend:
    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import mailgun  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError("Mailgun SDK backend requires the 'mailgun' package") from exc

        api_key = self._settings.EMAIL_MAILGUN_API_KEY
        domain = self._settings.EMAIL_MAILGUN_DOMAIN
        if not api_key or not domain:
            raise RuntimeError("Mailgun credentials are not configured")
        client = mailgun.Client(api_key=api_key)
        await asyncio.to_thread(
            client.messages.create,
            domain=domain,
            data={
                "from": self._settings.EMAIL_FROM,
                "to": list(message.recipients),
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            },
        )


__all__ = [
    "BrevoSDKEmailBackend",
    "MailgunSDKEmailBackend",
    "PostmarkSDKEmailBackend",
    "SendGridSDKEmailBackend",
]
