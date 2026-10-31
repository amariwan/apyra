# apyra-tasks

Background task primitives and adapters for Apyra.

## Installation

```bash
uv add apyra-tasks
uv add 'apyra-tasks[celery]' # Celery adapter
uv add 'apyra-tasks[taskiq]' # Taskiq adapter
```

`repeat_every` preserves its original `None` return by default. Set `return_task_handle=True` to receive a cancellable `asyncio.Task` when the decorated starter is awaited; keep and cancel/await that handle during application shutdown so periodic work has an explicit lifecycle.

Synchronous tasks and synchronous `on_exception`/`on_complete` callbacks run in a worker thread; async callbacks run on the event loop.

Cancelling the task stops future repetitions but cannot interrupt a synchronous callback already running in its worker thread. That callback can continue after the task handle finishes. Use a cooperative stop signal, such as a captured `threading.Event`, and wait for the callback to finish before closing resources it uses.

## License

MIT
