# Contributing to Apyra

Thanks for your interest in contributing. Apyra is a small, modular Python framework;
keep changes small, scoped, and consistent with the existing conventions.

## Prerequisites

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
uv sync --all-packages --all-extras
```

## Development workflow

1. Create a branch from `main`.
2. Make your change in the smallest possible scope.
3. Add or update tests for the behaviour you change.
4. Run the quality gates:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run pyright
   uv run pytest
   ```

5. Update documentation and package READMEs when behaviour changes.
6. Open a pull request using the provided template.

## Conventions

- `apyra-core` must not depend on FastAPI or any optional infrastructure package.
- Use PEP 420 implicit namespace packages: no `apyra/__init__.py` anywhere.
- Settings use pydantic-settings with the `APYRA_` env prefix.
- Ruff: line-length 100, target py312.
- Prefer small, composable functions and explicit dependencies.

## Tests

- Tests live next to packages (`packages/<name>/tests`) and in `tests/`.
- New behaviour should come with tests; bug fixes should include a regression test.

## Commit messages

Use clear, imperative commit messages (e.g. `Add cache decorator for async callables`).

## Pull requests

- Keep PRs focused and reviewable.
- Describe the motivation and the change.
- Link related issues.

## Code of conduct

By participating you agree to the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).