# Why Apyra?

FastAPI solves HTTP API ergonomics well. Enterprise services usually need more than routing: typed
settings, identity validation, persistence, background work, delivery semantics, observability, and
repeatable release controls. Apyra provides compatible building blocks without turning those choices
into hidden runtime magic.

## What Apyra optimizes for

- **Progressive adoption:** install individual distributions instead of a mandatory platform bundle.
- **Explicit composition:** application startup shows which adapters and resources are active.
- **Typed boundaries:** packages expose typed contracts and ship PEP 561 markers.
- **Operational honesty:** delivery, retry, scheduler, and cache limitations are documented rather
  than described as exactly-once guarantees.
- **Framework independence:** domain and application primitives do not depend on HTTP infrastructure.

## When it may not fit

Use plain FastAPI when the application needs only a few routes and no shared framework conventions.
Use a batteries-included framework when implicit ORM, administration, and template conventions are
more valuable than infrastructure choice. Apyra is intended for teams that want modular enterprise
capabilities while retaining control over composition.

The [architecture overview](../architecture/overview.md) describes the package boundaries.
