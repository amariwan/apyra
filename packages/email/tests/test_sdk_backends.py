import builtins
from types import ModuleType, SimpleNamespace
from typing import Any

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
    return EmailMessage(
        subject="hi",
        recipients=("a@example.com",),
        text="hello",
        html="<p>hi</p>",
        reply_to="reply@example.com",
    )


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


@pytest.mark.asyncio
async def test_mailgun_sdk_uses_api_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeMailgunClient:
        def __init__(self, *, auth: tuple[str, str]) -> None:
            captured["auth"] = auth
            self.messages = self

        def __enter__(self) -> object:
            return self

        def __exit__(self, *_exc_info: object) -> None:
            captured["closed"] = True

        def create(self, **kwargs: object) -> None:
            captured["message"] = kwargs

    mailgun_module = ModuleType("mailgun")
    mailgun_module.Client = FakeMailgunClient  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "mailgun", mailgun_module)
    settings = EmailSettings(
        EMAIL_FROM="from@example.com",
        EMAIL_MAILGUN_API_KEY="mailgun-secret",
        EMAIL_MAILGUN_DOMAIN="example.com",
    )

    await MailgunSDKEmailBackend(settings).send(message())

    assert captured["auth"] == ("api", "mailgun-secret")
    assert captured["message"] == {
        "domain": "example.com",
        "data": {
            "from": "from@example.com",
            "to": ["a@example.com"],
            "subject": "hi",
            "text": "hello",
            "html": "<p>hi</p>",
            "h:Reply-To": "reply@example.com",
        },
    }
    assert captured["closed"] is True


@pytest.mark.asyncio
async def test_sendgrid_sdk_sets_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    sendgrid = pytest.importorskip("sendgrid")
    captured: dict[str, object] = {}

    def capture_send(_client: object, mail: Any) -> None:
        captured.update(mail.get())

    monkeypatch.setattr(sendgrid.SendGridAPIClient, "send", capture_send)
    settings = EmailSettings(EMAIL_SENDGRID_API_KEY="key", EMAIL_FROM="from@example.com")

    await SendGridSDKEmailBackend(settings).send(message())

    assert captured["reply_to"] == {"email": "reply@example.com"}


@pytest.mark.asyncio
async def test_postmark_sdk_sets_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    postmarker = pytest.importorskip("postmarker.core")
    captured: dict[str, object] = {}

    def setup_managers(client: Any) -> None:
        def send_email(**kwargs: object) -> None:
            captured.update(kwargs)

        client.emails = SimpleNamespace(send=send_email)

    monkeypatch.setattr(postmarker.PostmarkClient, "_setup_managers", setup_managers)
    settings = EmailSettings(EMAIL_POSTMARK_SERVER_TOKEN="token", EMAIL_FROM="from@example.com")

    await PostmarkSDKEmailBackend(settings).send(message())

    assert captured["ReplyTo"] == "reply@example.com"


@pytest.mark.asyncio
async def test_brevo_sdk_sets_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    brevo = pytest.importorskip("sib_api_v3_sdk")
    captured: list[Any] = []

    def capture_send(_api: object, email: Any) -> None:
        captured.append(email)

    monkeypatch.setattr(brevo.TransactionalEmailsApi, "send_transac_email", capture_send)
    settings = EmailSettings(EMAIL_BREVO_API_KEY="key", EMAIL_FROM="from@example.com")

    await BrevoSDKEmailBackend(settings).send(message())

    assert captured[0].reply_to == {"email": "reply@example.com"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("backend_type", "import_name", "missing_module", "settings_values", "provider"),
    [
        (
            SendGridSDKEmailBackend,
            "sendgrid",
            "sendgrid",
            {"EMAIL_SENDGRID_API_KEY": "key"},
            "SendGrid",
        ),
        (
            PostmarkSDKEmailBackend,
            "postmarker.core",
            "postmarker",
            {"EMAIL_POSTMARK_SERVER_TOKEN": "token"},
            "Postmark",
        ),
        (
            BrevoSDKEmailBackend,
            "sib_api_v3_sdk",
            "sib_api_v3_sdk",
            {"EMAIL_BREVO_API_KEY": "key"},
            "Brevo",
        ),
        (
            MailgunSDKEmailBackend,
            "mailgun",
            "mailgun",
            {"EMAIL_MAILGUN_API_KEY": "key", "EMAIL_MAILGUN_DOMAIN": "example.com"},
            "Mailgun",
        ),
    ],
)
async def test_sdk_backends_report_missing_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    backend_type: type[Any],
    import_name: str,
    missing_module: str,
    settings_values: dict[str, object],
    provider: str,
) -> None:
    original_import = builtins.__import__

    def missing_sdk(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == import_name:
            raise ModuleNotFoundError(f"No module named '{missing_module}'", name=missing_module)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_sdk)
    settings = EmailSettings.model_validate({"EMAIL_FROM": "from@example.com", **settings_values})
    backend = backend_type(settings)

    with pytest.raises(RuntimeError, match=f"{provider} SDK backend requires"):
        await backend.send(message())


@pytest.mark.asyncio
async def test_sendgrid_propagates_nested_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def broken_sdk(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sendgrid":
            raise ModuleNotFoundError("missing nested sdk module", name="sendgrid.helpers")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_sdk)
    backend = SendGridSDKEmailBackend(
        EmailSettings(EMAIL_FROM="from@example.com", EMAIL_SENDGRID_API_KEY="key")
    )

    with pytest.raises(ModuleNotFoundError, match="missing nested sdk module"):
        await backend.send(message())
