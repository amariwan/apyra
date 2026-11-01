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
from apyra.workflow import WorkflowEngine, Workflow

engine = WorkflowEngine(repository=...)
```

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
