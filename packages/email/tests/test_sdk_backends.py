import pytest

from apyra.email import (
    BrevoSDKEmailBackend,
    EmailMessage,
    EmailSettings,
    MailgunSDKEmailBackend,
    PostmarkSDKEmailBackend,
    SendGridSDKEmailBackend,
)


class FakeClient:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def send(self, message: object) -> None:
        self.messages.append(message)


def message() -> EmailMessage:
    return EmailMessage(subject="hi", recipients=("a@example.com",), text="hello", html="<p>hi</p>")


@pytest.mark.asyncio
async def test_sdk_backends_use_injected_clients() -> None:
    settings = EmailSettings(EMAIL_FROM="from@example.com")
    for backend_cls in (
        SendGridSDKEmailBackend,
        PostmarkSDKEmailBackend,
        BrevoSDKEmailBackend,
        MailgunSDKEmailBackend,
    ):
        client = FakeClient()
        backend = backend_cls(settings, client=client)
        await backend.send(message())
        assert len(client.messages) == 1


@pytest.mark.asyncio
async def test_sendgrid_sdk_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "sendgrid", None)
    settings = EmailSettings(EMAIL_FROM="from@example.com", EMAIL_SENDGRID_API_KEY="key")
    backend = SendGridSDKEmailBackend(settings)
    with pytest.raises(RuntimeError):
        await backend.send(message())
