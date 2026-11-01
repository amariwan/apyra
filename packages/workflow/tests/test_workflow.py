from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from apyra.workflow.engine import WorkflowEngine
from apyra.workflow.models import WorkflowRecord
from apyra.workflow.repository import WorkflowRepository
from apyra.workflow.state import Workflow, WorkflowStatus

pytestmark = pytest.mark.asyncio


async def test_workflow_runs_to_completion() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        wf = Workflow(name="demo")
        wf_engine = WorkflowEngine(session)

        async def step_one(workflow: Workflow) -> str:
            return "done"

        await wf_engine.start(wf, [step_one])
        await session.commit()
        assert wf.status == WorkflowStatus.COMPLETED
    await engine.dispose()


async def test_workflow_failure_marks_failed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        wf = Workflow(name="failing")
        wf_engine = WorkflowEngine(session)

        async def failing_step(workflow: Workflow) -> None:
            raise RuntimeError("boom")

        await wf_engine.start(wf, [failing_step])
        await session.commit()
        assert wf.status == WorkflowStatus.FAILED
        assert wf.error == "boom"
    await engine.dispose()


async def test_expired_lease_recovery() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = WorkflowRepository(session)
        wf = Workflow(name="recover")
        record = await repo.create(wf)
        record.status = WorkflowStatus.RUNNING.value
        record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

        recovered = await repo.recover_expired()
        assert recovered == 1
        stored = await repo.get(wf.workflow_id)
        assert stored is not None
        assert stored.status == WorkflowStatus.PENDING.value
    await engine.dispose()
