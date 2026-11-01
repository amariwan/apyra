"""Workflow execution engine."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import WorkflowRepository
from .state import StepCallable, Workflow, WorkflowStatus, WorkflowStep


class WorkflowEngine:
    """Execute workflows step by step with persistence."""

    def __init__(self, session: AsyncSession, max_step_attempts: int = 3) -> None:
        self._session = session
        self._repository = WorkflowRepository(session)
        self._max_step_attempts = max_step_attempts

    async def start(self, workflow: Workflow, steps: Sequence[StepCallable]) -> Workflow:
        workflow.steps = [WorkflowStep(name=f"step-{i}") for i, _ in enumerate(steps)]
        await self._repository.create(workflow)
        await self._session.commit()
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
                step.attempts = attempt
                try:
                    result = await steps[workflow.current_step](workflow)
                    step.result = result
                    step.status = WorkflowStatus.COMPLETED
                    workflow.current_step += 1
                    await self._repository.update_status(
                        workflow.workflow_id,
                        WorkflowStatus.RUNNING,
                        current_step=workflow.current_step,
                    )
                    await self._session.commit()
                    break
                except Exception as exc:  # noqa: BLE001
                    step.error = str(exc)
                    if attempt >= self._max_step_attempts:
                        step.status = WorkflowStatus.FAILED
                        workflow.transition_to(WorkflowStatus.FAILED)
                        workflow.error = str(exc)
                        await self._repository.update_status(
                            workflow.workflow_id,
                            WorkflowStatus.FAILED,
                            current_step=workflow.current_step,
                            error=str(exc),
                        )
                        await self._session.commit()
                        return workflow
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
