"""Tenant context contracts for Apyra."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context for a request or operation."""

    tenant_id: str
    metadata: dict[str, str] = field(default_factory=lambda: {})  # noqa: PIE807


class TenantResolver(Protocol):
    """Resolve tenant context from an application-owned input."""

    def resolve(self, subject: object) -> TenantContext | None: ...


def require_tenant(context: TenantContext | None) -> TenantContext:
    """Return a tenant context or raise when it is missing."""
    if context is None:
        raise ValueError("tenant context is required")
    return context
