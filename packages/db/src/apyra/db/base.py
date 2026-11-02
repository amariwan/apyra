"""SQLAlchemy declarative base and reusable mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for application models."""


class TimestampMixin:
    """Add timezone-aware creation and update timestamps to a model."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantScopedMixin:
    """Add an indexed tenant identifier column to a multi-tenant model.

    Combine with :class:`apyra.db.TenantScopedRepository` so every query is
    automatically restricted to the current tenant rather than relying on callers
    to remember a tenant filter.
    """

    tenant_id: Mapped[str] = mapped_column(String(255), index=True)


class UUIDPrimaryKeyMixin:
    """Add a UUID primary key generated when a model is created."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
