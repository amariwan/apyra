"""Adversarial multi-tenancy isolation tests.

These tests verify that tenant context is request/task-scoped and fail-closed:
concurrent async tasks must never observe another task's tenant, and code that
requires a tenant must fail when none is set.
"""

from __future__ import annotations

import asyncio

import pytest

from apyra.security import (
    TenantContext,
    get_current_tenant,
    require_tenant,
    reset_current_tenant,
    set_current_tenant,
)


async def test_tenant_context_is_isolated_across_concurrent_tasks() -> None:
    async def worker(tenant_id: str) -> str:
        token = set_current_tenant(TenantContext(tenant_id=tenant_id))
        try:
            # Yield several times so tasks interleave; the contextvar must stay task-local.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            current = get_current_tenant()
            assert current is not None
            return current.tenant_id
        finally:
            reset_current_tenant(token)

    results = await asyncio.gather(*(worker(f"tenant-{index}") for index in range(20)))
    assert results == [f"tenant-{index}" for index in range(20)]


async def test_tenant_context_does_not_leak_after_task_completion() -> None:
    async def scoped() -> None:
        token = set_current_tenant(TenantContext(tenant_id="tenant-a"))
        try:
            assert get_current_tenant() is not None
        finally:
            reset_current_tenant(token)

    await scoped()
    # After the task completes and resets, the parent context is unaffected.
    assert get_current_tenant() is None


def test_require_tenant_fails_closed_without_context() -> None:
    # A background job with no tenant context must fail closed, not default to a tenant.
    with pytest.raises(ValueError, match="tenant context is required"):
        require_tenant(get_current_tenant())
