# CLI guide

The `apyra` command currently provides project creation, focused code generators, configuration
checks, and database command placeholders.

## Create a project

```bash
uv run apyra new my-api
uv run apyra new my-api --template cookie-auth
uv run apyra new my-api --template modular-monolith
uv run apyra new my-api --template distributed
uv run apyra new --interactive
uv run apyra new my-api --with-db --with-observability
uv run apyra new my-api --all-features
```

Supported templates are `minimal`, `cookie-auth`, `modular-monolith`, and `distributed`. The
cookie-auth template validates access tokens supplied by an external identity provider and adds
signed double-submit CSRF protection; it does not implement login or token issuance. The
modular-monolith and distributed templates scaffold clean-architecture and enterprise reference
applications respectively.

The CLI refuses to overwrite an existing project unless `--force` is explicit.

## Feature toggles for the minimal template

The default `minimal` template can be extended with optional capabilities using feature flags:

- `--with-db` enables the database package and a SQLite-backed `DatabaseManager`.
- `--with-auth` enables the authentication package.
- `--with-cache` enables the cache package.
- `--with-messaging` enables the messaging package.
- `--with-observability` enables structured logging configuration.
- `--all-features` enables every optional capability at once.

Feature flags only affect the `minimal` template; the other templates already include their
own curated dependency sets. The interactive builder also asks which features to enable when
the minimal template is selected.

## Generate code

```bash
uv run apyra generate module orders
uv run apyra generate model Order
uv run apyra generate router orders
uv run apyra generate service Order
uv run apyra generate schema Order
uv run apyra generate repository Order
uv run apyra generate crud Order --dry-run
uv run apyra generate resource Order
uv run apyra generate usecase CreateOrder
```

Each generator supports `--dry-run` and `--force`. Names must be valid Python identifiers; path
traversal and Python keywords are rejected. Generated repository and model code requires the
database package and must be integrated into the application's composition root explicitly.

## Inspect authoritative help

```bash
uv run apyra --help
uv run apyra new --help
uv run apyra generate --help
```

The CLI exposes an interactive builder (`apyra new --interactive`), `apyra doctor`, and `--dry-run`
for every generator. Generated code is a starting point and must be integrated into the
application's composition root.

## Startup banner

Interactive terminals print a startup banner with the framework version and environment on every
invocation. The banner is disabled automatically in CI, for `apyra doctor --json`, and whenever
stdout is not a terminal. It can also be turned off explicitly with `--no-banner` or
`APYRA_NO_BANNER=1`. Install the optional `rich` extra (`apyra-cli[rich]`) for colored output;
without it the banner renders as plain text.
