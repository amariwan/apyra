# Apyra

> Modular Python framework for building FastAPI applications with explicit, composable infrastructure.

Apyra is a **uv-workspace monorepo** of 16 independently publishable Python packages under the
`apyra.*` namespace. Instead of one large framework, you install only the pieces you need —
core primitives, FastAPI wiring, database access, auth, storage, cache, AI, observability,
email, realtime channels, i18n, events, security, background tasks, and a developer CLI —
and compose them explicitly.

**Python ≥ 3.12 · MIT · FastAPI · async-first**

## Why Apyra?

- **Modular by design.** `apyra-core` has zero FastAPI/infra dependencies. Add packages only
  when you need them.
- **Explicit composition.** Application factories and adapters are wired by you, not by hidden
  globals or magic.
- **Independently publishable.** Every package ships its own wheel; pin and upgrade them
  separately.
- **Type-safe.** Strict mypy + pyright across the workspace.
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
| `apyra-observability` | Logging and observability primitives |
| `apyra-email` | Email delivery primitives and providers |
| `apyra-channels` | Realtime channel primitives and pub/sub |
| `apyra-i18n` | Internationalization primitives |
| `apyra-events` | Typed event bus and Redis Streams support |
| `apyra-tasks` | Background task primitives and adapters |
| `apyra-security` | Security primitives |
| `apyra-cli` | Developer CLI |
| `apyra` | Metapackage with installation bundles |

## Quick start (5 minutes)

### 1. Install

```bash
# With uv (recommended)
uv add apyra            # metapackage with all bundles
# or pick only what you need
uv add apyra-core apyra-fastapi
```

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
uv run uvicorn main:app --app-dir examples/minimal-api --host 0.0.0.0 --port 5000 --reload
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

> Note: `just check` calls `test-all`, which currently collects no tests. Use the
> command above (or `just lint` + the individual tools) until that is fixed.

## Architecture

Apyra is a standalone monorepo with independently publishable distributions.

- `apyra` (metapackage) → `apyra-fastapi` → `apyra-core`
- Optional infrastructure packages depend only on what they need.
- `apyra-core` never depends on FastAPI or any optional infrastructure.
- PEP 420 implicit namespace packages: no `apyra/__init__.py` anywhere; each concrete
  subpackage (e.g. `apyra.core`) has its own `__init__.py`.

See [`docs/architecture/overview.md`](docs/architecture/overview.md).

## Roadmap

- [ ] Stabilize public APIs and versioning policy
- [ ] Publish packages to PyPI
- [ ] Expand examples (auth, db, storage, cache, events, tasks)
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