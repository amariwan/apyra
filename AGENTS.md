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
- Tests: `uv run pytest` or `just test-all` run the full suite. Marker-filtered `just test-unit` and `just test-integration` are not representative until tests are marked.
- Full gate: `just check` runs lint, mypy, pyright, and `uv run pytest`.
- Build: CI and `just build` both build core fastapi storage db auth cache ai observability email channels i18n events security tasks cli, then apyra.
- Install sanity: `uv build --package apyra-<name>` then install wheels into a fresh venv and import `apyra.<name>`.

## Conventions

- Settings use pydantic-settings with env prefix `APYRA_` and load `.env` / `.env.local`.
- Ruff: line-length 100, target py312, src = packages/tests/examples; ignores S101, N999. Per-package pytest config sets `pythonpath = ["src"]`.
- mypy lists most namespace packages explicitly in root `pyproject.toml`; pyright covers `packages` and `tests` in basic mode. Review both configurations when adding packages.
- Metapackage `apyra` has `module-name = []` (no source); its import surface comes from `apyra-core`'s namespace package. `apyra[all]` pulls all optional packages.
- Examples use editable path sources (`[tool.uv.sources]`), not workspace membership.
