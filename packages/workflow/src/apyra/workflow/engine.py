"""Workflow execution engine.

Execution semantics
-------------------

* Steps run sequentially and each step's completion is committed before the next
  step starts, so a crash never repeats a completed step (at-most-once per commit).
* ``current_step`` and per-step state are persisted; :meth:`resume` reconstructs a
  workflow from storage and continues from the first incomplete step.
* Each step can be given a timeout (``step_timeout_seconds``); a timed-out step is
  retried up to ``max_step_attempts`` and then fails the workflow. Cancellation
  propagates and leaves the workflow ``RUNNING``, so it can be resumed.

Durability is **experimental**: the engine does not currently coordinate across
multiple workers claiming the same workflow, and step handlers must be idempotent
because a step that fails after its side effects (but before commit) may re-run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import WorkflowRepository
from .state import StepCallable, Workflow, WorkflowStatus, WorkflowStep


def _handler_identity(handler: StepCallable) -> str:
    """Return a stable callable identity suitable for persisted workflow validation."""
    explicit_id = getattr(handler, "workflow_step_id", None)
    if isinstance(explicit_id, str) and explicit_id:
        return f"{type(handler).__module__}:{explicit_id}"

    module = getattr(handler, "__module__", None)
    qualified_name = getattr(handler, "__qualname__", None)
    if not isinstance(module, str) or not isinstance(qualified_name, str):
        handler_type = type(handler)
        module = handler_type.__module__
        qualified_name = handler_type.__qualname__
    return f"{module}:{qualified_name}"


class WorkflowEngine:
    """Execute workflows step by step with persistence."""

    def __init__(
        self,
        session: AsyncSession,
        max_step_attempts: int = 3,
        step_timeout_seconds: float | None = None,
    ) -> None:
        self._session = session
        self._repository = WorkflowRepository(session)
        self._max_step_attempts = max_step_attempts
        self._step_timeout_seconds = step_timeout_seconds

    async def start(self, workflow: Workflow, steps: Sequence[StepCallable]) -> Workflow:
        workflow.steps = [
            WorkflowStep(name=f"step-{index}", handler_id=_handler_identity(handler))
            for index, handler in enumerate(steps)
        ]
        await self._repository.create(workflow)
        await self._session.commit()
        await self.run(workflow, steps)
        return workflow

    async def resume(self, workflow_id: str, steps: Sequence[StepCallable]) -> Workflow | None:
        """Reconstruct a workflow from storage and continue from its current step."""
        workflow = await self._repository.reconstruct(workflow_id)
        if workflow is None:
            return None
        if workflow.status == WorkflowStatus.COMPLETED:
            return workflow
        if workflow.status not in (
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
            WorkflowStatus.FAILED,
        ):
            raise ValueError(f"workflow in {workflow.status.value} state cannot be resumed")
        if len(steps) != len(workflow.steps):
            raise ValueError("resume step sequence does not match persisted workflow steps")
        persisted_handler_ids = [step.handler_id for step in workflow.steps]
        if any(handler_id is None for handler_id in persisted_handler_ids):
            raise ValueError("persisted workflow step identity is missing; refusing unsafe resume")
        if [_handler_identity(handler) for handler in steps] != persisted_handler_ids:
            raise ValueError("resume handler sequence does not match persisted workflow steps")
        if not 0 <= workflow.current_step <= len(workflow.steps):
            raise ValueError("persisted current_step is outside the workflow step sequence")
        if workflow.status == WorkflowStatus.FAILED:
            workflow.transition_to(WorkflowStatus.PENDING)
            workflow.error = None
        if workflow.current_step < len(workflow.steps):
            current_step = workflow.steps[workflow.current_step]
            if current_step.status in (WorkflowStatus.FAILED, WorkflowStatus.RUNNING):
                current_step.status = WorkflowStatus.PENDING
                current_step.error = None
        await self.run(workflow, steps)
        return workflow

    async def run(self, workflow: Workflow, steps: Sequence[StepCallable]) -> Workflow:
        if workflow.status == WorkflowStatus.PENDING:
            workflow.transition_to(WorkflowStatus.RUNNING)
        await self._repository.update_status(
            workflow.workflow_id, WorkflowStatus.RUNNING, current_step=workflow.current_step
        )
        await self._session.commit()
        while workflow.current_step < len(steps):
            step = workflow.steps[workflow.current_step]
            step.status = WorkflowStatus.RUNNING
            attempt = 0
            while attempt < self._max_step_attempts:
                attempt += 1
                step.attempts += 1
                step.error = None
                try:
                    coroutine = steps[workflow.current_step](workflow)
                    if self._step_timeout_seconds is not None:
                        result = await asyncio.wait_for(
                            coroutine, timeout=self._step_timeout_seconds
                        )
                    else:
                        result = await coroutine
                    step.result = result
                    step.status = WorkflowStatus.COMPLETED
                    workflow.current_step += 1
                    await self._repository.update_steps(workflow)
                    await self._repository.update_status(
                        workflow.workflow_id,
                        WorkflowStatus.RUNNING,
                        current_step=workflow.current_step,
                    )
                    await self._session.commit()
                    break
                except TimeoutError:
                    step.error = f"step timed out after {self._step_timeout_seconds}s"
                    if attempt >= self._max_step_attempts:
                        step.status = WorkflowStatus.FAILED
                        workflow.transition_to(WorkflowStatus.FAILED)
                        workflow.error = step.error
                        await self._repository.update_steps(workflow)
                        await self._repository.update_status(
                            workflow.workflow_id,
                            WorkflowStatus.FAILED,
                            current_step=workflow.current_step,
                            error=step.error,
                        )
                        await self._session.commit()
                        return workflow
                    await self._repository.update_steps(workflow)
                    await self._session.commit()
                except Exception as exc:  # noqa: BLE001
                    step.error = str(exc)
                    if attempt >= self._max_step_attempts:
                        step.status = WorkflowStatus.FAILED
                        workflow.transition_to(WorkflowStatus.FAILED)
                        workflow.error = str(exc)
                        await self._repository.update_steps(workflow)
                        await self._repository.update_status(
                            workflow.workflow_id,
                            WorkflowStatus.FAILED,
                            current_step=workflow.current_step,
                            error=str(exc),
                        )
                        await self._session.commit()
                        return workflow
                    await self._repository.update_steps(workflow)
                    await self._session.commit()
            if step.status != WorkflowStatus.COMPLETED:
                continue
        if workflow.status != WorkflowStatus.FAILED:
            workflow.transition_to(WorkflowStatus.COMPLETED)
            workflow.result = workflow.steps[-1].result if workflow.steps else None
            await self._repository.update_status(
                workflow.workflow_id,
                WorkflowStatus.COMPLETED,
                current_step=workflow.current_step,
                result=workflow.result,
            )
            await self._session.commit()
        return workflow

    async def compensate(
        self, workflow: Workflow, compensations: Sequence[StepCallable]
    ) -> Workflow:
        workflow.transition_to(WorkflowStatus.COMPENSATING)
        await self._repository.update_status(workflow.workflow_id, WorkflowStatus.COMPENSATING)
        await self._session.commit()
        for compensation in reversed(compensations):
            try:
                await compensation(workflow)
            except Exception as exc:  # noqa: BLE001
                workflow.error = str(exc)
                workflow.transition_to(WorkflowStatus.FAILED)
                await self._repository.update_status(
                    workflow.workflow_id, WorkflowStatus.FAILED, error=str(exc)
                )
                await self._session.commit()
                return workflow
        workflow.transition_to(WorkflowStatus.COMPENSATED)
        await self._repository.update_status(workflow.workflow_id, WorkflowStatus.COMPENSATED)
        await self._session.commit()
        return workflow
