# apyra

Metapackage for Apyra with installation bundles. Re-exports the `apyra.*`
namespace packages.

## Installation

```bash
uv add apyra                 # core only; add packages as needed
uv add 'apyra[all]'          # every Apyra package
uv add 'apyra[production]'   # FastAPI integration and observability
uv add apyra-core apyra-fastapi  # pick individual packages
```

The metapackage's extras (`web`, `database`, `storage`, `auth`, `cache`, `ai`,
`observability`, `email`, `channels`, `events`, `security`, `tasks`, `i18n`,
and `cli`) each install the corresponding package. Infrastructure-specific
drivers remain optional extras on their respective packages.

## License

MIT
