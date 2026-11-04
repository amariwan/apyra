"""Tenant context contracts for Apyra."""

from __future__ import annotations

from contextvars import ContextVar, Token
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


_current_tenant: ContextVar[TenantContext | None] = ContextVar("apyra_current_tenant", default=None)


def get_current_tenant() -> TenantContext | None:
    """Return the tenant context for the current async context, if any."""
    return _current_tenant.get()


def set_current_tenant(context: TenantContext | None) -> Token[TenantContext | None]:
    """Set the request-scoped tenant context and return a reset token."""
    return _current_tenant.set(context)


def reset_current_tenant(token: Token[TenantContext | None]) -> None:
    """Restore the previous tenant context from a :func:`set_current_tenant` token."""
    _current_tenant.reset(token)
