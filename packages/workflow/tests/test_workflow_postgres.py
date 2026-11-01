from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from apyra.workflow.engine import WorkflowEngine
from apyra.workflow.models import WorkflowRecord
from apyra.workflow.repository import WorkflowRepository
from apyra.workflow.state import Workflow, WorkflowStatus

DATABASE_URL = os.getenv("APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg:///apyra_test")


def _postgres_available() -> bool:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        async def check() -> bool:
            try:
                engine = create_async_engine(DATABASE_URL)
                async with engine.connect() as conn:
                    await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
                await engine.dispose()
                return True
            except Exception:  # noqa: BLE001
                return False

        return asyncio.run(check())
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.postgres,
    pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable"),
]


async def _create_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowRecord.metadata.drop_all)
        await conn.run_sync(WorkflowRecord.metadata.create_all)


async def test_workflow_persistence_and_transition() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        wf = Workflow(name="pg-demo")
        wf_engine = WorkflowEngine(session)

        async def step_one(workflow: Workflow) -> str:
            return "ok"

        await wf_engine.start(wf, [step_one])
        await session.commit()
        stored = await WorkflowRepository(session).get(wf.workflow_id)
        assert stored is not None
        assert stored.status == WorkflowStatus.COMPLETED.value
    await engine.dispose()


async def test_expired_lease_recovery_postgres() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = WorkflowRepository(session)
        wf = Workflow(name="recover")
        record = await repo.create(wf)
        record.status = WorkflowStatus.RUNNING.value
        record.lease_expires_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ) - __import__("datetime").timedelta(seconds=1)
        await session.commit()

        recovered = await repo.recover_expired()
        assert recovered == 1
        stored = await repo.get(wf.workflow_id)
        assert stored is not None
        assert stored.status == WorkflowStatus.PENDING.value
    await engine.dispose()
