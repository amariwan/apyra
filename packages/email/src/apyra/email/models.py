"""Provider-neutral email values."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EmailMessage:
    subject: str
    recipients: tuple[str, ...]
    text: str
    html: str | None = None
    reply_to: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "recipients": list(self.recipients),
            "text": self.text,
            "html": self.html,
            "reply_to": self.reply_to,
            "headers": dict(self.headers),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> EmailMessage:
        raw_recipients = payload.get("recipients", [])
        raw_headers = payload.get("headers", {})
        if not isinstance(raw_recipients, list) or not all(
            isinstance(item, str) for item in raw_recipients
        ):
            raise ValueError("Email recipients must be a list of strings")
        if not isinstance(raw_headers, dict) or not all(
            isinstance(name, str) and isinstance(value, str) for name, value in raw_headers.items()
        ):
            raise ValueError("Email headers must be a string mapping")
        subject = payload.get("subject")
        text = payload.get("text")
        html = payload.get("html")
        reply_to = payload.get("reply_to")
        if not isinstance(subject, str) or not isinstance(text, str):
            raise ValueError("Email subject and text must be strings")  # noqa: TRY004
        if html is not None and not isinstance(html, str):
            raise ValueError("Email html must be a string or null")
        if reply_to is not None and not isinstance(reply_to, str):
            raise ValueError("Email reply_to must be a string or null")
        return cls(
            subject=subject,
            recipients=tuple(raw_recipients),
            text=text,
            html=html,
            reply_to=reply_to,
            headers={str(name): str(value) for name, value in raw_headers.items()},
        )


__all__ = ["EmailMessage"]
