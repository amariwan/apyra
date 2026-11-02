# apyra-workflow

Persistent workflow orchestration primitives for Apyra.

## Purpose

`apyra-workflow` provides a workflow model, status tracking, repository, and engine for durable, multi-step workflow orchestration backed by a database.

## Installation

```bash
uv add apyra-workflow
```

## Minimal usage

```python
from sqlalchemy.ext.asyncio import AsyncSession

from apyra.workflow import Workflow, WorkflowEngine


async def run_workflow(session: AsyncSession) -> None:
    engine = WorkflowEngine(session)

    async def step_one(workflow: Workflow) -> str:
        return "done"

    workflow = await engine.start(Workflow(name="order"), [step_one])
    assert workflow.status.value == "completed"
```

## Durability guarantees

Steps run sequentially and each completed step is committed before the next starts, so a
crash never repeats a completed step. `WorkflowRepository.reconstruct` and
`WorkflowEngine.resume` rebuild a workflow from storage and continue from the first
incomplete step.

Durability across multiple workers is **experimental**: the engine does not yet coordinate
workers claiming the same workflow, and step handlers must be idempotent because a step that
fails after its side effects (but before commit) may re-run.

## Optional dependencies

None (requires `apyra-db` and SQLAlchemy, pulled transitively).

## Configuration

Uses `apyra-db` session management for persistence.

## Public API

- `Workflow`, `WorkflowStatus`, `WorkflowStep`
- `WorkflowEngine`
- `WorkflowRecord`
- `WorkflowRepository`

## Error behavior

Workflow failures propagate from the engine; persistence errors from `apyra-db`.

## Integration

Requires `apyra-db` (transitive). Combine with `apyra-application` for step logic. Integration tests require PostgreSQL.

## Compatibility

- Python ≥ 3.12

## License

MIT
