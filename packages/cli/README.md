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

None (depends on `apyra-core`).

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
