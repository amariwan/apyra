from __future__ import annotations

import asyncio
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


async def test_workflow_step_state_is_reconstructed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        wf = Workflow(name="partial")
        wf_engine = WorkflowEngine(session, max_step_attempts=1)

        async def step_one(workflow: Workflow) -> str:
            return "one"

        async def step_two(workflow: Workflow) -> str:
            raise RuntimeError("boom")

        await wf_engine.start(wf, [step_one, step_two])
        await session.commit()
        assert wf.status == WorkflowStatus.FAILED

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = WorkflowRepository(session)
        reconstructed = await repo.reconstruct(wf.workflow_id)
        assert reconstructed is not None
        assert reconstructed.status == WorkflowStatus.FAILED
        assert reconstructed.current_step == 1
        assert reconstructed.steps[0].status == WorkflowStatus.COMPLETED
        assert reconstructed.steps[0].result == "one"
        assert reconstructed.steps[1].status == WorkflowStatus.FAILED
    await engine.dispose()


async def test_workflow_step_timeout_marks_failed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        wf = Workflow(name="timeout")
        wf_engine = WorkflowEngine(session, max_step_attempts=1, step_timeout_seconds=0.01)

        async def hanging_step(workflow: Workflow) -> str:
            await asyncio.sleep(10)
            return "never"

        await wf_engine.start(wf, [hanging_step])
        await session.commit()
        assert wf.status == WorkflowStatus.FAILED
        assert wf.error is not None and "timed out" in wf.error
    await engine.dispose()
