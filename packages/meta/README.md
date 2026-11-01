# apyra (metapackage)

Metapackage and installation bundles for Apyra.

## Purpose

`apyra` is the metapackage that installs `apyra-core` plus optional bundles via extras. It has no source module of its own; its import surface comes from `apyra-core`'s namespace package.

## Installation

```bash
uv add apyra                # core only
uv add "apyra[all]"         # all packages
uv add "apyra[web]"         # FastAPI bundle
uv add "apyra[database]"    # database bundle
```

## Available extras

`web`, `database`, `storage`, `auth`, `cache`, `ai`, `observability`, `email`, `channels`, `all` (and more). See `pyproject.toml` for the full list.

## Minimal usage

```python
import apyra.core  # namespace package provided by apyra-core
```

## Configuration

Inherits from each installed package.

## Public API

None directly; re-exports come from `apyra-core`.

## Error behavior

N/A (metapackage).

## Integration

Use as a convenience installer; production apps may pin individual `apyra-*` packages.

## Compatibility

- Python ≥ 3.12

## License

MIT
