"""Typed event definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _empty_payload() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event name, JSON-compatible payload, and occurrence timestamp."""

    name: str
    payload: dict[str, object] = field(default_factory=_empty_payload)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def decode_occurred_at(value: object) -> datetime:
    """Parse a timezone-aware ISO timestamp, or use the current UTC time."""
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            pass
        else:
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed
    return datetime.now(UTC)
