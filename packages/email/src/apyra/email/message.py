"""Email message model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: tuple[str, ...]
    subject: str
    body: str
    from_address: str | None = None
    html: bool = False
    attachments: tuple[bytes, ...] = field(default_factory=tuple)
