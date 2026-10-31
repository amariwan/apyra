# Apyra

[![CI](https://github.com/amariwan/apyra/actions/workflows/ci.yml/badge.svg)](https://github.com/amariwan/apyra/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/amariwan/apyra?style=social)](https://github.com/amariwan/apyra/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/amariwan/apyra)](https://github.com/amariwan/apyra/commits/main)

> Modular Python framework for building FastAPI applications with explicit, composable infrastructure.

Apyra is a **uv-workspace monorepo** of 16 independently publishable Python packages under the
`apyra.*` namespace. Instead of one large framework, you install only the pieces you need —
core primitives, FastAPI wiring, database access, auth, storage, cache, AI, observability,
email, realtime channels, i18n, events, security, background tasks, and a developer CLI —
and compose them explicitly.

**Python ≥ 3.12 · MIT · FastAPI · async-first**

## What Apyra adds to FastAPI

FastAPI already provides routing, dependency injection, and OpenAPI. Apyra is **not a replacement for FastAPI**: it packages optional backend infrastructure so applications can compose the integrations they actually need. Start with a small app and add database, authentication, storage, or events only when the use case calls for them.

**Project status:** Early-stage (v0.1.0 source). APIs and package availability may change before a stable release. For now, the most reliable way to evaluate Apyra is to run the examples from this repository.

## Why Apyra?

- **Modular by design.** `apyra-core` has zero FastAPI/infra dependencies. Add packages only
  when you need them.
- **Explicit composition.** Application factories and adapters are wired by you, not by hidden
  globals or magic.
- **Independently publishable.** Every package ships its own wheel; pin and upgrade them
  separately.
- **Typed distributions.** Inline PEP 561 types ship with each code package; mypy and Pyright
  run in CI across the configured package sets.
- **Production-oriented.** Async database repositories, JWT/OAuth2/RBAC, storage contracts,
  cache decorators, observability primitives, typed events, and background task adapters.

## Package overview

| Package | What it provides |
|---|---|
| `apyra-core` | Settings, errors, framework primitives |
| `apyra-fastapi` | FastAPI application factory and HTTP adapters |
| `apyra-db` | Async database infrastructure and repositories |
| `apyra-auth` | JWT, OAuth2/OIDC, RBAC, authorization policies |
| `apyra-storage` | Storage contracts, filesystem/S3 backends |
| `apyra-cache` | Cache contracts, adapters, decorators |
| `apyra-ai` | OpenAI-compatible AI client |
| `apyra-observability` | Logging, error, and performance monitoring primitives |
| `apyra-email` | Email delivery primitives and providers |
| `apyra-channels` | Realtime channel primitives and pub/sub |
| `apyra-i18n` | Internationalization primitives |
| `apyra-events` | Typed event bus and Redis Streams support |
| `apyra-tasks` | Background task primitives and adapters |
| `apyra-security` | Security primitives |
| `apyra-cli` | Developer CLI |
| `apyra` | Metapackage with installation bundles |

## Quick start (5 minutes)

PyPI packages are not published yet. Try the bundled example from the source checkout:

```bash
# With uv (recommended)
uv add apyra-core apyra-fastapi
# Optional: the apyra metapackage provides additional dependency bundles.
```

If the packages are not yet available on PyPI, clone this repository and use the
workspace setup below instead. Do not assume a PyPI release exists.

### 2. Create an app

```python
from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

router = APIRouter()


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from Apyra"}


app = create_app(
    title="My API",
    routers=[router],
    settings=Settings(api_prefix="/api"),
)
```

### 3. Run

```bash
git clone https://github.com/amariwan/apyra.git
cd apyra
uv sync --all-packages --all-extras
uv run uvicorn main:app --app-dir examples/minimal-api --host 127.0.0.1 --port 5000 --reload
```

Then open <http://localhost:5000/docs>.

A complete runnable example lives in [`examples/minimal-api`](examples/minimal-api).
An authenticated example (JWT issuance + role/scope guards) lives in
[`examples/authenticated-api`](examples/authenticated-api).
A database-backed example (SQLite + repository CRUD) lives in
[`examples/database-api`](examples/database-api).
A storage example (filesystem upload/download) lives in
[`examples/storage-api`](examples/storage-api).
A cache example (`@cached` decorator) lives in
[`examples/cache-api`](examples/cache-api).
An events example (typed event bus) lives in
[`examples/events-api`](examples/events-api).

## Development

```bash
uv sync --all-packages --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Run the full quality gate (lint + typecheck + tests):

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pyright && uv run pytest
```

> The `just check` recipe runs lint, mypy, pyright, and the normal pytest suite.
> The marker-filtered `just test-unit` and `just test-integration` recipes are not
> equivalent to the full suite until all tests have appropriate markers.
## Architecture

Apyra is a standalone monorepo with independently publishable distributions.

- `apyra` (metapackage) → `apyra-core`; the optional `web` extra adds
  `apyra-fastapi` (which also depends on `apyra-auth`).
- Optional infrastructure packages depend only on what they need.
- `apyra-core` never depends on FastAPI or any optional infrastructure.
- PEP 420 implicit namespace packages: no `apyra/__init__.py` anywhere; each concrete
  subpackage (e.g. `apyra.core`) has its own `__init__.py`.

See [`docs/architecture/overview.md`](docs/architecture/overview.md).

## Roadmap

- [ ] Stabilize public APIs and versioning policy
- [ ] Publish packages to PyPI
- [x] Add runnable examples for auth, database, storage, cache, and events
- [ ] Add a runnable tasks example
- [ ] Add integration tests across package boundaries
- [ ] Improve package-level READMEs and API docs
- [ ] Add a documentation site

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Good first issues are labelled [`good first issue`](https://github.com/amariwan/apyra/labels/good%20first%20issue)
and [`help wanted`](https://github.com/amariwan/apyra/labels/help%20wanted).

## Community & support

- Issues: bug reports and feature requests
- Discussions: questions and design proposals
- Security: see [`SECURITY.md`](SECURITY.md) (report privately, no public issues)

## License

MIT — see [`LICENSE`](LICENSE).

---

If Apyra is useful to you, please consider giving the repository a ⭐. It helps others
discover the project and motivates continued maintenance.
