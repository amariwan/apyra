import pytest

from apyra.email import ConsoleEmailBackend, EmailDispatcher, EmailMessage


@pytest.mark.asyncio
async def test_console_backend_captures_message() -> None:
    backend = ConsoleEmailBackend()
    dispatcher = EmailDispatcher(backend)
    message = EmailMessage(subject="hi", recipients=("a@example.com",), text="hello")
    await dispatcher.send(message)
    assert backend.sent == [message]
