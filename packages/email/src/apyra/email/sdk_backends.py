"""Optional SDK-backed email delivery backends."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from apyra.email.models import EmailMessage
from apyra.email.settings import EmailSettings


class SendGridSDKEmailBackend:
    """Deliver messages through the optional SendGrid SDK integration."""

    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        """Send one message with the SendGrid SDK, offloading its sync client."""
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import sendgrid  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
            from sendgrid.helpers.mail import (  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
                Content,
                Email,
                Mail,
                To,
            )
        except ModuleNotFoundError as exc:
            if exc.name != "sendgrid":
                raise
            raise RuntimeError("SendGrid SDK backend requires the 'sendgrid' package") from exc

        api_key = self._settings.EMAIL_SENDGRID_API_KEY
        if not api_key:
            raise RuntimeError("SendGrid API key is not configured")
        mail: Any = cast(
            Any,
            Mail(
                from_email=Email(self._settings.EMAIL_FROM),
                to_emails=[To(recipient) for recipient in message.recipients],
                subject=message.subject,
                plain_text_content=Content("text/plain", message.text),
            ),
        )
        if message.reply_to:
            mail.reply_to = Email(message.reply_to)
        if message.html:
            mail.add_content(Content("text/html", message.html))
        client: Any = cast(Any, sendgrid.SendGridAPIClient(api_key))
        await asyncio.to_thread(client.send, mail)


class PostmarkSDKEmailBackend:
    """Deliver messages through the optional Postmark SDK integration."""

    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        """Send one message with the Postmark SDK, offloading its sync client."""
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            from postmarker.core import PostmarkClient  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
        except ModuleNotFoundError as exc:
            if exc.name != "postmarker":
                raise
            raise RuntimeError("Postmark SDK backend requires the 'postmarker' package") from exc

        token = self._settings.EMAIL_POSTMARK_SERVER_TOKEN
        if not token:
            raise RuntimeError("Postmark server token is not configured")
        client: Any = PostmarkClient(server_token=token)
        payload = {
            "From": self._settings.EMAIL_FROM,
            "To": ", ".join(message.recipients),
            "Subject": message.subject,
            "TextBody": message.text,
            "HtmlBody": message.html,
        }
        if message.reply_to:
            payload["ReplyTo"] = message.reply_to
        await asyncio.to_thread(client.emails.send, **payload)


class BrevoSDKEmailBackend:
    """Deliver messages through the optional Brevo SDK integration."""

    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        """Send one message with the Brevo SDK, offloading its sync client."""
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import sib_api_v3_sdk  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
        except ModuleNotFoundError as exc:
            if exc.name != "sib_api_v3_sdk":
                raise
            raise RuntimeError("Brevo SDK backend requires the 'sib-api-v3-sdk' package") from exc

        api_key = self._settings.EMAIL_BREVO_API_KEY
        if not api_key:
            raise RuntimeError("Brevo API key is not configured")
        configuration: Any = cast(Any, sib_api_v3_sdk.Configuration())
        configuration.api_key["api-key"] = api_key
        api_client: Any = cast(Any, sib_api_v3_sdk.ApiClient(configuration))
        api_instance: Any = cast(Any, sib_api_v3_sdk.TransactionalEmailsApi(api_client))
        email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"email": self._settings.EMAIL_FROM},
            to=[{"email": recipient} for recipient in message.recipients],
            subject=message.subject,
            text_content=message.text,
            html_content=message.html,
            reply_to={"email": message.reply_to} if message.reply_to else None,
        )
        await asyncio.to_thread(api_instance.send_transac_email, email)


class MailgunSDKEmailBackend:
    """Deliver messages through the optional Mailgun SDK integration."""

    def __init__(self, settings: EmailSettings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        """Send one message with the Mailgun SDK, offloading its sync client."""
        if self._client is not None:
            await asyncio.to_thread(self._client.send, message)
            return

        try:
            import mailgun  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
        except ModuleNotFoundError as exc:
            if exc.name != "mailgun":
                raise
            raise RuntimeError("Mailgun SDK backend requires the 'mailgun' package") from exc

        api_key = self._settings.EMAIL_MAILGUN_API_KEY
        domain = self._settings.EMAIL_MAILGUN_DOMAIN
        if not api_key or not domain:
            raise RuntimeError("Mailgun credentials are not configured")

        def _send() -> None:
            data = {
                "from": self._settings.EMAIL_FROM,
                "to": list(message.recipients),
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            }
            if message.reply_to:
                data["h:Reply-To"] = message.reply_to
            with mailgun.Client(auth=("api", api_key)) as client:
                client.messages.create(
                    domain=domain,
                    data=data,
                )

        await asyncio.to_thread(_send)


__all__ = [
    "BrevoSDKEmailBackend",
    "MailgunSDKEmailBackend",
    "PostmarkSDKEmailBackend",
    "SendGridSDKEmailBackend",
]
