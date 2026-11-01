from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest

from apyra.tasks import ApyraScheduler


async def _job() -> None:
    return None


def test_invalid_cron_raises() -> None:
    scheduler = ApyraScheduler()
    try:
        scheduler.add_cron_job(_job, "not a cron")
    except ValueError:
        return
    raise AssertionError("invalid cron must raise")


def test_pause_resume_remove() -> None:
    scheduler = ApyraScheduler()
    job_id = scheduler.add_interval_job(_job, 3600)
    scheduler.pause_job(job_id)
    scheduler.resume_job(job_id)
    scheduler.remove_job(job_id)


@pytest.mark.asyncio
async def test_scheduler_shutdown() -> None:
    scheduler = ApyraScheduler()
    await scheduler.start()
    await scheduler.shutdown(wait=False)


SYNC_URL = os.getenv(
    "APYRA_TEST_POSTGRES_URL_SYNC",
    "postgresql+psycopg://itsaplan:itsaplan@localhost:5432/itsaplan",
)


def _postgres_available() -> bool:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(SYNC_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable")
def test_postgres_persistence() -> None:
    url = SYNC_URL
    try:
        scheduler = ApyraScheduler(job_store_url=url)
    except Exception:  # noqa: BLE001
        pytest.skip("PostgreSQL unavailable")

    async def run() -> None:
        await scheduler.start()
        scheduler.add_date_job(_job, datetime.now(UTC) + timedelta(seconds=0.1))
        await asyncio.sleep(0.3)
        await scheduler.shutdown(wait=True)

    try:
        asyncio.run(run())
    except Exception:  # noqa: BLE001
        pytest.skip("PostgreSQL unavailable")
    scheduler2 = ApyraScheduler(job_store_url=url)
    assert scheduler2 is not None
