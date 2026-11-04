"""Workflow repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WorkflowRecord
from .state import Workflow, WorkflowStatus, WorkflowStep


def _serialize_step(step: WorkflowStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "handler_id": step.handler_id,
        "status": step.status.value,
        "result": step.result,
        "error": step.error,
        "attempts": step.attempts,
        "compensation_error": step.compensation_error,
    }


def _deserialize_step(data: dict[str, Any]) -> WorkflowStep:
    return WorkflowStep(
        name=data.get("name", ""),
        handler_id=data.get("handler_id"),
        status=WorkflowStatus(data.get("status", WorkflowStatus.PENDING.value)),
        result=data.get("result"),
        error=data.get("error"),
        attempts=int(data.get("attempts", 0)),
        compensation_error=data.get("compensation_error"),
    )


class WorkflowRepository:
    """Persist and recover workflow instances."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, workflow: Workflow) -> WorkflowRecord:
        record = WorkflowRecord(
            id=workflow.workflow_id,
            name=workflow.name,
            status=workflow.status.value,
            current_step=workflow.current_step,
            steps=[_serialize_step(step) for step in workflow.steps],
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get(self, workflow_id: str) -> WorkflowRecord | None:
        result = await self._session.execute(
            select(WorkflowRecord).where(WorkflowRecord.id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def reconstruct(self, workflow_id: str) -> Workflow | None:
        """Rebuild an in-memory ``Workflow`` (including step state) from storage."""
        record = await self.get(workflow_id)
        if record is None:
            return None
        workflow = Workflow(
            workflow_id=record.id,
            name=record.name,
            status=WorkflowStatus(record.status),
            current_step=record.current_step,
            result=record.result,
            error=record.error,
        )
        workflow.steps = [_deserialize_step(data) for data in (record.steps or [])]
        return workflow

    async def update_status(
        self,
        workflow_id: str,
        status: WorkflowStatus,
        current_step: int | None = None,
        error: str | None = None,
        result: object | None = None,
    ) -> None:
        record = await self.get(workflow_id)
        if record is None:
            raise ValueError("workflow not found")
        record.status = status.value
        if current_step is not None:
            record.current_step = current_step
        record.error = error
        if result is not None:
            record.result = result
        await self._session.flush()

    async def update_steps(self, workflow: Workflow) -> None:
        """Persist the workflow's per-step status, results, and attempt counts."""
        record = await self.get(workflow.workflow_id)
        if record is None:
            raise ValueError("workflow not found")
        record.steps = [_serialize_step(step) for step in workflow.steps]
        await self._session.flush()

    async def claim_pending(
        self, worker_id: str, limit: int, lease_seconds: int
    ) -> Sequence[WorkflowRecord]:
        now = datetime.now(UTC)
        lease_until = now + timedelta(seconds=lease_seconds)
        stmt = (
            select(WorkflowRecord)
            .where(WorkflowRecord.status == WorkflowStatus.PENDING.value)
            .order_by(WorkflowRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        records = list(result.scalars().all())
        for record in records:
            record.status = WorkflowStatus.RUNNING.value
            record.lease_expires_at = lease_until
            record.leased_by = worker_id
            record.fencing_token = uuid.uuid4().hex
        await self._session.flush()
        return records

    async def recover_expired(self) -> int:
        now = datetime.now(UTC)
        stmt = (
            select(WorkflowRecord)
            .where(
                WorkflowRecord.status == WorkflowStatus.RUNNING.value,
                WorkflowRecord.lease_expires_at.is_not(None),
                WorkflowRecord.lease_expires_at < now,
            )
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        records = list(result.scalars().all())
        for record in records:
            record.status = WorkflowStatus.PENDING.value
            record.lease_expires_at = None
            record.leased_by = None
            record.fencing_token = None
        await self._session.flush()
        return len(records)
