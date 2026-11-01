"""Audit event contracts for Apyra."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit record for a security-relevant action."""

    actor: str
    action: str
    target: str
    outcome: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str | None = None
    correlation_id: str | None = None


class AuditLogger(Protocol):
    """Persist or publish an audit event."""

    async def record(self, event: AuditEvent) -> None: ...
