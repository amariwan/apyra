# Testing

Run local validation inside the required Devcontainer:

```bash
devcontainer exec --workspace-folder . just check
```

The full gate runs Ruff lint/format checks, mypy, Pyright, and the complete pytest suite. Focused
commands are useful during development but do not replace the final suite:

```bash
devcontainer exec --workspace-folder . uv run pytest packages/auth/tests -q
devcontainer exec --workspace-folder . uv run pytest -m postgres -q
devcontainer exec --workspace-folder . uv run pytest -m redis -q
```

Tests marked `postgres` or `redis` require real services. A skip means the scenario is unverified.
Do not replace concurrency, locking, delivery, or recovery tests with mocks or SQLite.

For packaging changes, build every distribution and install wheels into a fresh virtual environment.
For generator changes, create a project in a temporary directory, install only built artifacts, run
its tests/type checks, and import the ASGI application.

Documentation validation uses `just docs-check` and treats warnings as errors:

```bash
devcontainer exec --workspace-folder . just docs-check
```

## Docker-backed test services

PostgreSQL and Redis integration tests require real services. Start the project-owned services using
the repository's documented container workflow and run the tests from the Devcontainer. A skipped
service test is unverified; SQLite and mocks do not establish PostgreSQL or Redis guarantees.
