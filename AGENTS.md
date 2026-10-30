# AGENTS.md

## Project

Apyra: uv workspace monorepo of 16 independently publishable Python packages under `packages/*` (namespace `apyra.*`). Python >=3.12. PEP 420 implicit namespace packages: no `apyra/__init__.py` anywhere; each subpackage (e.g. `apyra.core`) has its own `__init__.py`. `apyra-core` must not depend on FastAPI or any infra package.

## Setup

```bash
uv sync --all-packages --all-extras
```

## Commands

- Dev server: `just dev` (uvicorn on examples/minimal-api, port 5000, reload) or `uv run uvicorn main:app --app-dir examples/minimal-api --host 0.0.0.0 --port 5000 --reload`.
- Lint: `uv run ruff check .` then `uv run ruff format --check .` (`just lint`).
- Format: `uv run ruff format .` (`just fmt`); auto-fix: `uv run ruff check --fix .` (`just fix`).
- Typecheck: `uv run mypy` and `uv run pyright` (both must pass; CI runs both on 3.12 and 3.13).
- Tests: `uv run pytest` (69 tests). Do NOT use `just test-unit`/`test-integration`/`test-all` or `pytest -m ...`: the unit/integration/packaging markers are declared but never applied to tests, so those commands collect zero tests.
- Full gate: run `just lint`, `uv run mypy`, `uv run pyright`, `uv run pytest` (do not rely on `just check`, which calls the empty `test-all`).
- Build: CI builds all packages: core fastapi storage db auth cache ai observability email channels i18n events security tasks cli, then apyra. `just build` omits i18n/events/security/tasks/cli — use the CI list.
- Install sanity: `uv build --package apyra-<name>` then install wheels into a fresh venv and import `apyra.<name>`.

## Conventions

- Settings use pydantic-settings with env prefix `APYRA_` and load `.env` / `.env.local`.
- Ruff: line-length 100, target py312, src = packages/tests/examples; ignores S101, N999. Per-package pytest config sets `pythonpath = ["src"]`.
- mypy checks only 9 packages (core, fastapi, storage, db, auth, cache, observability, channels, ai); pyright covers all of `packages` and `tests`. New packages may need adding to mypy `packages`/`mypy_path`.
- Metapackage `apyra` has `module-name = []` (no source); its import surface comes from `apyra-core`'s namespace package. `apyra[all]` pulls all optional packages.
- Examples use editable path sources (`[tool.uv.sources]`), not workspace membership.
