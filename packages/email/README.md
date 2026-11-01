# apyra-email

Email delivery primitives for Apyra.

## Purpose

`apyra-email` provides an email message model, backend contract, and implementations for SMTP, SES, SendGrid, Mailgun, Postmark, Brevo, and console, plus SDK variants, Celery/queue dispatchers, and factory helpers.

## Installation

```bash
uv add apyra-email                                 # core
uv add "apyra-email[providers]"                    # + httpx, boto3
uv add "apyra-email[sdk]"                          # + provider SDKs
uv add "apyra-email[celery]"                        # + Celery
```

## Minimal usage

```python
from apyra.email import EmailMessage, get_email_dispatcher

dispatcher = get_email_dispatcher()
await dispatcher.send(EmailMessage(to=["user@example.com"], subject="Hi", text="Hello"))
```

## Optional dependencies

- `celery`: `celery>=5.5.0`
- `providers`: `httpx>=0.27.0`, `boto3>=1.34.0`
- `sdk`: `sendgrid`, `postmarker`, `sib-api-v3-sdk`, `mailgun`

## Configuration

`EmailSettings` / `EmailBackendName` via Pydantic Settings (`apyra.email.settings`).

## Public API

Backends: `EmailBackend`, `ConsoleEmailBackend`, `SMTPEmailBackend`, `SESEmailBackend`, `SendGridEmailBackend`, `MailgunEmailBackend`, `PostmarkEmailBackend`, `BrevoEmailBackend`, plus SDK variants. Dispatch: `EmailDispatcher`, `EmailQueue`, `CeleryEmailQueue`, `EmailDeliveryMode`. Factory: `build_email_backend`, `get_email_dispatcher`, `close_email_dispatcher`. Models/settings: `EmailMessage`, `EmailSettings`, `EmailBackendName`.

## Error behavior

Backend delivery errors propagate; configuration errors raise during backend construction.

## Integration

Use `get_email_dispatcher()` in application lifespan. Combine with `apyra-tasks` for async delivery.

## Compatibility

- Python ≥ 3.12
- Email loads `.env.dev`

## License

MIT
