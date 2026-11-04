from __future__ import annotations

import asyncio
import os
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv(
    "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
)
MIGRATION_DIRECTORY = Path(__file__).resolve().parents[2] / "docs" / "migrations" / "sql"
MIGRATION_PATHS = (
    MIGRATION_DIRECTORY / "0.1.0-release-hardening.sql",
    MIGRATION_DIRECTORY / "0.1.0-postgres-idempotency.sql",
)


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(DATABASE_URL)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 - used only to decide whether to skip this integration test
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.postgres,
    pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable"),
]


async def test_release_migration_upgrades_existing_rows() -> None:
    engine = create_async_engine(DATABASE_URL)
    schema = f"release_migration_{uuid.uuid4().hex}"
    outbox_id = uuid.uuid4()
    idempotency_id = uuid.uuid4()
    migration = re.sub(
        r"--[^\n]*",
        "",
        "\n".join(path.read_text(encoding="utf-8") for path in MIGRATION_PATHS),
    )
    statements = [statement.strip() for statement in migration.split(";") if statement.strip()]

    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            await connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            await connection.exec_driver_sql(
                """CREATE TABLE apyra_outbox (
                    id UUID PRIMARY KEY, destination VARCHAR(255) NOT NULL,
                    payload JSON NOT NULL, status VARCHAR(32) NOT NULL,
                    attempts INTEGER NOT NULL, next_attempt_at TIMESTAMPTZ NOT NULL,
                    lease_expires_at TIMESTAMPTZ, delivered_at TIMESTAMPTZ,
                    last_error VARCHAR(1000), created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )"""
            )
            await connection.exec_driver_sql(
                """CREATE TABLE apyra_workflows (
                    id VARCHAR(36) PRIMARY KEY, name VARCHAR(255) NOT NULL,
                    status VARCHAR(32) NOT NULL, current_step INTEGER NOT NULL,
                    steps JSON NOT NULL, result JSON, error VARCHAR(2000),
                    lease_expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )"""
            )
            await connection.execute(
                text("""INSERT INTO apyra_outbox
                    (id, destination, payload, status, attempts, next_attempt_at,
                     created_at, updated_at)
                    VALUES (:id, 'orders', '{"order_id": 7}', 'pending', 0,
                            now(), now(), now())"""),
                {"id": outbox_id},
            )
            await connection.execute(
                text("""INSERT INTO apyra_workflows
                    (id, name, status, current_step, steps, created_at, updated_at)
                    VALUES ('existing-workflow', 'existing', 'pending', 0, '[]', now(), now())""")
            )
            for statement in statements:
                await connection.exec_driver_sql(statement)
            await connection.execute(
                text("""INSERT INTO apyra_idempotency (message_id, status, expires_at)
                    VALUES (:id, 'processing', now())"""),
                {"id": idempotency_id},
            )

            outbox = (
                await connection.execute(
                    text(
                        "SELECT leased_by, fencing_token, version_id "
                        "FROM apyra_outbox WHERE id = :id"
                    ),
                    {"id": outbox_id},
                )
            ).one()
            workflow = (
                await connection.execute(
                    text("SELECT leased_by, fencing_token, version_id FROM apyra_workflows")
                )
            ).one()
            indexes = (
                await connection.execute(
                    text(
                        "SELECT to_regclass('ix_apyra_outbox_poll'), "
                        "to_regclass('ix_apyra_outbox_lease')"
                    )
                )
            ).one()
            idempotency_created = await connection.scalar(
                text("SELECT created_at FROM apyra_idempotency WHERE message_id = :id"),
                {"id": idempotency_id},
            )

            assert outbox == (None, None, 0)
            assert workflow == (None, None, 0)
            assert indexes == ("ix_apyra_outbox_poll", "ix_apyra_outbox_lease")
            assert idempotency_created is not None
    finally:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await engine.dispose()
