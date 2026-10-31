# apyra-email

Email delivery primitives and providers for Apyra.

## Installation

```bash
uv add apyra-email
uv add 'apyra-email[providers]' # HTTP providers and AWS SES
uv add 'apyra-email[sdk]'       # provider SDK integrations
uv add 'apyra-email[celery]'    # Celery queue integration
```

SMTP and the console backend use the standard library and need no extra. HTTP provider backends
require the `providers` extra; the optional SDK-backed implementations require `sdk`.

## Configure and send

The console backend is the default for local development. Configure SMTP through environment
variables or the package's `.env` / `.env.dev` files:

```dotenv
EMAIL_BACKEND=smtp
EMAIL_FROM=notifications@example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=notifications@example.com
EMAIL_SMTP_PASSWORD=...
```

Send a message through the cached dispatcher and close its queue client once during application
shutdown:

```python
from apyra.email import (
    EmailDeliveryMode,
    EmailMessage,
    close_email_dispatcher,
    get_email_dispatcher,
)


async def send_welcome_email(recipient: str) -> EmailDeliveryMode:
    return await get_email_dispatcher().send(
        EmailMessage(
            subject="Welcome",
            recipients=(recipient,),
            text="Thanks for signing up.",
        )
    )


async def shutdown_email() -> None:
    await close_email_dispatcher()
```

Set `EMAIL_ENABLED=false` to disable delivery. The dispatcher then skips backend and queue
initialization, and `send()` returns `EmailDeliveryMode.DISABLED`. Provider and Celery settings are
not required while email is disabled.

Queue delivery falls back to direct sending by default when enqueueing raises an exception. Set
`EMAIL_QUEUE_FALLBACK_TO_DIRECT=false` to propagate that exception without making a direct send; this
avoids one duplicate-delivery path when a broker accepted a message but its acknowledgement was
lost. The result is still ambiguous, so caller retries can also produce duplicates; exactly-once
delivery requires idempotency in the queue and worker.

## License

MIT
