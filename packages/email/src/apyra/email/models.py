"""Provider-neutral email values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast


def _empty_headers() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Immutable provider-neutral email content and recipient data."""

    subject: str
    recipients: tuple[str, ...]
    text: str
    html: str | None = None
    reply_to: str | None = None
    headers: Mapping[str, str] = field(default_factory=_empty_headers)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-compatible representation for queue transport."""
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
        """Validate and reconstruct a message from a queue payload."""
        raw_recipients = payload.get("recipients", [])
        raw_headers = payload.get("headers", {})
        if not isinstance(raw_recipients, list):
            raise ValueError("Email recipients must be a list of strings")  # noqa: TRY004
        recipients: list[str] = []
        for item in cast(list[object], raw_recipients):
            if not isinstance(item, str):
                raise ValueError("Email recipients must be a list of strings")  # noqa: TRY004
            recipients.append(item)
        if not isinstance(raw_headers, dict):
            raise ValueError("Email headers must be a string mapping")  # noqa: TRY004
        headers: dict[str, str] = {}
        for name, value in cast(dict[object, object], raw_headers).items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise ValueError("Email headers must be a string mapping")  # noqa: TRY004
            headers[name] = value
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
            recipients=tuple(recipients),
            text=text,
            html=html,
            reply_to=reply_to,
            headers=headers,
        )


__all__ = ["EmailMessage"]
