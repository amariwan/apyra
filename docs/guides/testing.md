# Testing

Run project validation natively (no Docker or Devcontainer required):

```bash
just check
```

The full gate runs Ruff lint/format checks, mypy, Pyright, and the complete pytest suite. Focused
commands are useful during development but do not replace the final suite:

```bash
uv run pytest packages/auth/tests -q
uv run pytest -m postgres -q
uv run pytest -m redis -q
```

Tests marked `postgres` or `redis` require real services. A skip means the scenario is unverified.
Do not replace concurrency, locking, delivery, or recovery tests with mocks or SQLite.

For packaging changes, build every distribution and install wheels into a fresh virtual environment.
For generator changes, create a project in a temporary directory, install only built artifacts, run
its tests/type checks, and import the ASGI application.

Documentation validation uses `just docs-check` and treats warnings as errors.

## Optional: Devcontainer

For a reproducible, isolated development environment, you can run tests inside the optional
Devcontainer:

```bash
devcontainer exec --workspace-folder . just check
devcontainer exec --workspace-folder . uv run pytest packages/auth/tests -q
```

## Optional: Docker Infrastructure

PostgreSQL and Redis integration tests require real services. You can start them with Docker
Compose or install them locally. Core development does not require Docker.