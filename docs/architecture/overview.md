# Apyra Architecture

Apyra is developed as a standalone monorepo with independently publishable Python
distributions.

## Package dependency direction

```text
apyra (metapackage)
  -> apyra-core

apyra[web]
  -> apyra-fastapi
       -> apyra-core
       -> apyra-auth
```

Optional infrastructure packages will depend only on the packages they actually
need. `apyra-core` must not depend on FastAPI or any optional infrastructure.

## Namespace packages

Apyra uses PEP 420 implicit namespace packages. There is no `apyra/__init__.py`
in any package. Each concrete subpackage, such as `apyra.core` and
`apyra.fastapi`, contains its own `__init__.py`.

## Scope

Apyra delivers 20 independently publishable distributions:

- `apyra-core`
- `apyra-domain`
- `apyra-application`
- `apyra-fastapi`
- `apyra-db`
- `apyra-auth`
- `apyra-storage`
- `apyra-cache`
- `apyra-ai`
- `apyra-observability`
- `apyra-email`
- `apyra-channels`
- `apyra-i18n`
- `apyra-events`
- `apyra-messaging`
- `apyra-tasks`
- `apyra-workflow`
- `apyra-security`
- `apyra-cli`
- `apyra` (metapackage)
