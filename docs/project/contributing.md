# Contributing

## Required development environment

Use the Devcontainer for local development, dependency management, builds, and tests. Keep
project-specific Python packages, virtual environments, and development services off the macOS host.

```bash
git clone https://github.com/amariwan/apyra.git
cd apyra
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . uv sync --all-packages --all-extras
```

Before coding, read the repository `AGENTS.md` and the mandatory
[Engineering Standards](engineering-standards.md). Preserve the package dependency direction. In
particular, `apyra-core` must not depend on FastAPI or infrastructure packages, and the PEP 420
namespace must not gain an `apyra/__init__.py`.

To run commands in the open Devcontainer:

```bash
devcontainer exec --workspace-folder . just check
devcontainer exec --workspace-folder . just docs-check
```

## Required checks

```bash
devcontainer exec --workspace-folder . just check
devcontainer exec --workspace-folder . just docs-check
```

Run real PostgreSQL/Redis integration tests for affected infrastructure. Add tests before behavior
changes and keep public APIs backward compatible unless a reviewed migration explicitly permits a
break.

## Documentation

Update the relevant guide and package reference when changing public behavior. API pages are
generated from package-level exports and docstrings; improve the owning source instead of duplicating
symbol descriptions in Markdown.

Follow `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` at the repository root for review,
conduct, and private vulnerability reporting.
