"""SQLAlchemy workflow persistence model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from apyra.db.base import Base, TimestampMixin
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .state import WorkflowStatus


class WorkflowRecord(Base, TimestampMixin):
    """Persisted workflow instance."""

    __tablename__ = "apyra_workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default=WorkflowStatus.PENDING.value)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    result: Mapped[Any] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
