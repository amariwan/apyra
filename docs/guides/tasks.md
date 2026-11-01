# Background tasks

`apyra-tasks` provides task contracts, Celery and Taskiq adapters, periodic helpers, and persistent
scheduler primitives.

```bash
uv add 'apyra-tasks[celery]'
# or
uv add 'apyra-tasks[taskiq]'
```

## Periodic work lifecycle

`repeat_every` keeps its compatibility return value of `None` by default. Set
`return_task_handle=True` to retain a cancellable `asyncio.Task`, then cancel and await it during
application shutdown.

Synchronous tasks and callbacks run in worker threads. Cancelling the asyncio handle cannot interrupt
a synchronous callback already executing; use a cooperative stop signal and wait for owned resources
before closing them.

## Delivery semantics

Broker-backed tasks and persistent schedules can be delivered more than once after worker crashes or
acknowledgement loss. Make handlers idempotent, bound retries, record terminal failures, and test
multi-worker recovery with the actual broker and database.
