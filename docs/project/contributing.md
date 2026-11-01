# Contributing

## Development setup

Native development is the default. No Docker or Devcontainer is required:

```bash
git clone https://github.com/amariwan/apyra.git
cd apyra
uv sync --all-packages --all-extras
```

Keep changes scoped and preserve the package dependency direction. In particular, `apyra-core` must
not depend on FastAPI or infrastructure packages, and the PEP 420 namespace must not gain an
`apyra/__init__.py`.

### Optional: Devcontainer

For a reproducible, isolated development environment, you can use the optional Devcontainer:

```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . uv sync --all-packages --all-extras
```

## Required checks

```bash
just check
just docs-check
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