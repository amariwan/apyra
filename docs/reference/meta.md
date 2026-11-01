# `apyra` metapackage

The `apyra` distribution is an installation bundle with no module source of its own. The import
surface is provided by independently installed PEP 420 namespace packages such as `apyra.core` and
`apyra.fastapi`.

Available extras group web, database, storage, authentication, cache, AI, observability, email,
channels, events, security, tasks, internationalization, CLI, and broader production/all bundles.
Infrastructure drivers remain optional extras of their owning packages.

Prefer explicit package dependencies in libraries and services that need a small surface. Use a
metapackage bundle only when its complete dependency set is intentional.
