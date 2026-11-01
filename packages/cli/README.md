# apyra-cli

Developer CLI for Apyra.

## Purpose

`apyra-cli` provides the `apyra` command-line tool: project scaffolding, code generation, and developer diagnostics.

## Installation

```bash
uv add apyra-cli
# or: pip install apyra-cli
```

The console script `apyra` is registered automatically.

## Minimal usage

```bash
apyra --help
apyra new my-api
apyra doctor
```

## Optional dependencies

- `rich` — enables colored terminal output for the startup banner (`apyra-cli[rich]`).
- `redis` — enables live Redis connectivity checks in `apyra doctor`.

## Startup banner

Interactive terminals show a startup banner with the framework version and environment:

```text
    _    ____
   / \  |  _ \ _   _ _ __ __ _
  / _ \ | |_) | | | | '__/ _` |
 / ___ \|  __/| |_| | | | (_| |
/_/   \_\_|    \__, |_|  \__,_|
                |___/
Apyra 0.1.0  ·  environment: development
```

The banner is cosmetic and never interferes with automation. It is rendered only when
stdout is an interactive terminal and is disabled automatically when:

- the `--no-banner` flag is passed,
- `APYRA_NO_BANNER=1` is set in the environment,
- a CI system is detected (for example `CI`, `GITHUB_ACTIONS`, or `GITLAB_CI`),
- the command emits machine-readable JSON (`apyra doctor --json`), or
- stdout is redirected or piped (a non-TTY).

When Rich is not installed the banner falls back to plain, uncolored text. The banner is
written to stdout only; it never goes through the logging pipeline, so production server
logs stay clean.

## Configuration

CLI commands resolve project settings from the working directory and environment files.

## Public API

- `main` — CLI entry point

## Error behavior

CLI errors are reported with non-zero exit codes and actionable messages. `--dry-run` avoids file writes.

## Integration

Generates projects that depend on `apyra.*` packages. Templates are validated in CI.

## Compatibility

- Python ≥ 3.12

## License

MIT
