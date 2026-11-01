# apyra-tasks

Background task primitives for Apyra.

## Purpose

`apyra-tasks` provides task definitions, a task runner, Celery/Taskiq adapters, and an APScheduler-based persistent scheduler with optional extras.

## Installation

```bash
uv add apyra-tasks                  # core
uv add "apyra-tasks[celery]"        # + Celery
uv add "apyra-tasks[taskiq]"        # + Taskiq
uv add "apyra-tasks[scheduler]"     # + APScheduler
```

## Minimal usage

```python
from apyra.tasks import Task, TaskRunner

runner = TaskRunner()
```

## Optional dependencies

- `celery`: `celery>=5.5.0`
- `taskiq`: `taskiq>=0.11.0`
- `scheduler`: `apscheduler>=3.11.0`

## Configuration

Scheduler persistence uses `apyra-db`. Adapter availability depends on installed extras.

## Public API

- `Task`, `TaskResult`, `TaskRunner`
- `CeleryAdapter`, `CeleryUnavailableError`
- `TaskiqAdapter`, `TaskiqUnavailableError`
- `ApyraScheduler`, `repeat_every`

## Error behavior

Missing optional adapters raise `*UnavailableError`. Task failures propagate from the runner.

## Integration

Combine with `apyra-db` for persistent scheduling and `apyra-fastapi` for triggering tasks.

## Compatibility

- Python ≥ 3.12
- Scheduler integration tests require PostgreSQL

## License

MIT
