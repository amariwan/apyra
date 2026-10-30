import httpx
import pytest

from apyra.email import (
    BrevoEmailBackend,
    EmailBackendName,
    EmailMessage,
    EmailSettings,
    MailgunEmailBackend,
    PostmarkEmailBackend,
    SendGridEmailBackend,
    SESEmailBackend,
)


def message() -> EmailMessage:
    return EmailMessage(subject="hi", recipients=("a@example.com",), text="hello", html="<p>hi</p>")


@pytest.mark.asyncio
async def test_sendgrid_backend_posts_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/mail/send"
        assert request.headers["authorization"] == "Bearer sg-key"
        return httpx.Response(202)

    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.SENDGRID,
        EMAIL_SENDGRID_API_KEY="sg-key",
        EMAIL_FROM="from@example.com",
    )
    backend = SendGridEmailBackend(settings, transport=httpx.MockTransport(handler))
    await backend.send(message())


@pytest.mark.asyncio
async def test_mailgun_backend_posts_form() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/v3/example.com/messages" in str(request.url)
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200)

    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.MAILGUN,
        EMAIL_MAILGUN_API_KEY="mg-key",
        EMAIL_MAILGUN_DOMAIN="example.com",
        EMAIL_FROM="from@example.com",
    )
    backend = MailgunEmailBackend(settings, transport=httpx.MockTransport(handler))
    await backend.send(message())


@pytest.mark.asyncio
async def test_postmark_backend_posts_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/email"
        assert request.headers["x-postmark-server-token"] == "pm-token"
        return httpx.Response(200)

    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.POSTMARK,
        EMAIL_POSTMARK_SERVER_TOKEN="pm-token",
        EMAIL_FROM="from@example.com",
    )
    backend = PostmarkEmailBackend(settings, transport=httpx.MockTransport(handler))
    await backend.send(message())


@pytest.mark.asyncio
async def test_brevo_backend_posts_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/smtp/email"
        assert request.headers["api-key"] == "brevo-key"
        return httpx.Response(201)

    settings = EmailSettings(
        EMAIL_BACKEND=EmailBackendName.BREVO,
        EMAIL_BREVO_API_KEY="brevo-key",
        EMAIL_FROM="from@example.com",
    )
    backend = BrevoEmailBackend(settings, transport=httpx.MockTransport(handler))
    await backend.send(message())


@pytest.mark.asyncio
async def test_ses_backend_uses_client() -> None:
    class FakeSESClient:
        def __init__(self) -> None:
            self.kwargs = None

        def send_email(self, **kwargs):
            self.kwargs = kwargs

    client = FakeSESClient()
    settings = EmailSettings(EMAIL_BACKEND=EmailBackendName.SES, EMAIL_FROM="from@example.com")
    backend = SESEmailBackend(settings, client=client)
    await backend.send(message())
    assert client.kwargs is not None
    assert client.kwargs["Destination"]["ToAddresses"] == ["a@example.com"]
