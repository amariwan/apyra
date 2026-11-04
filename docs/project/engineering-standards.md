# Apyra Engineering Standards

**Status: mandatory.** This guide is the detailed companion to the repository
`AGENTS.md`. It turns Apyra's architecture, security, reliability,
and compatibility priorities into rules for day-to-day implementation.

The terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative:

- **MUST / MUST NOT** are release-blocking requirements.
- **SHOULD** is the default. Deviations need a concrete reason and must be visible in review.
- **MAY** describes an allowed choice where the use case and existing package convention decide.

When a general principle conflicts with an existing public contract, package boundary, or explicit
repository instruction, preserve the contract and raise the conflict for review. Do not silently
change public behavior to make code look more uniform.

## 1. Before changing code

1. Read the root `AGENTS.md` and this guide. Locate the owning distribution, its `pyproject.toml`,
   source, public exports, tests, documentation, and direct dependents.
2. Inspect current behavior and the worktree before editing. Preserve all unrelated and uncommitted
   changes.
3. Search for an existing contract or implementation before adding another abstraction.
4. State the behavior being changed, relevant compatibility boundary, and evidence that will verify
   it. Keep the patch to the smallest complete change.
5. Use the Devcontainer for local development, tests, builds, and dependency operations as required
   by `AGENTS.md`.

## 2. Architecture and package boundaries

Apyra is a uv workspace of independently publishable distributions under `packages/`. Discover
the current inventory from the workspace and package manifests; do not rely on a fixed package
count. Every distribution owns its dependency declarations, optional extras, tests, public exports,
and package documentation.

The namespace is PEP 420:

- MUST NOT add a top-level `apyra/__init__.py`.
- Each concrete namespace, such as `apyra.core`, owns its own `__init__.py`.
- Keep public exports deliberate and small. Update `__all__` where the package uses it.

Dependencies point toward stable inner contracts, but the diagram is guidance rather than a
requirement to create every layer in every feature:

- `apyra-core` MUST stay independent of FastAPI, databases, brokers, and infrastructure packages.
- Domain code MUST NOT import HTTP frameworks, database models/sessions, brokers, or application
  implementations.
- Application use cases depend on domain concepts and abstractions. They MUST NOT require a
  concrete adapter to compile or to run their unit tests.
- Infrastructure adapters implement contracts and translate between external representations
  and internal models.
- FastAPI, CLI, and application composition are outer boundaries. They assemble dependencies and
  translate inputs, outputs, and errors; they do not own reusable business rules.
- A package MUST declare every direct project dependency it imports. Optional integrations MUST
  remain optional extras unless every installation requires them.
- Before adding an import, verify it against the owning distribution's `pyproject.toml` and the
  architecture-boundary tests. Do not create circular dependencies or import a sibling package
  merely because it is installed in the workspace.

Prefer dependency inversion and composition. Do not add empty layers, generic managers, service
locators, or interfaces with one implementation unless a real boundary, substitution, or test
requirement justifies them. Use the existing application `UseCase` Protocol and package contracts
where they fit.

### Cross-package composition

Packages MUST remain independently understandable, testable, and publishable. Integration means
composing their public contracts at an outer boundary; it does not mean merging modules or making
every package import every other package.

- Keep reusable behavior in its owning package. A package MUST NOT copy another package's
  authentication, authorization, logging, persistence, or retry implementation to avoid using its
  contract.
- Use a lower-level contract or `Protocol` when an inner package needs a capability. Concrete
  implementations are provided by adapters at application composition. Do not make domain or core
  import FastAPI, `apyra-auth`, `apyra-security`, or `apyra-observability` merely to call an optional
  integration.
- The composition root wires each required capability once and makes the wiring visible. For
  example, configure logging there with `apyra.observability.configure_logging`, provide
  authentication and authorization dependencies to HTTP adapters, and inject persistence or audit
  implementations into use cases that require them. Avoid hidden global registries and service
  locators.
- Keep authentication and authorization distinct: authentication establishes a trusted identity;
  authorization checks the requested action against that identity and the resource or tenant scope.
  Transport adapters may obtain identity from `apyra-fastapi`; policy and tenant decisions must use
  the owning `apyra-auth` / `apyra-security` contracts. A role or tenant value supplied by a caller
  is not trusted evidence by itself.
- Propagate request, principal, and tenant context explicitly through the established request
  context or function contracts. Do not add mutable process-global state or pass web-specific
  request objects into domain and application code.
- A cross-package feature MUST declare the dependency at the layer that actually needs it, preserve
  optional extras, and include tests at both seams: the owning package's contract behavior and the
  outer composition/integration behavior. Keep each package's unit tests runnable without unrelated
  adapters or infrastructure.
- When changing a shared contract, search all implementations and consumers, update them together,
  and check architecture tests, public exports, package metadata, docs, and compatibility. Do not
  silently introduce a second contract for the same capability.

## 3. Python code and functions

### Python and formatting

- Target Python 3.12 or newer. Follow root Ruff, mypy, and Pyright configuration; Ruff owns import
  ordering and formatting, with a 100-character line limit.
- Use `snake_case` for modules, functions, and variables; `PascalCase` for classes and types;
  `UPPER_SNAKE_CASE` for module constants.
- Prefer precise built-in generics and `collections.abc` interfaces. Public functions and methods
  MUST declare parameter and return types.
- Avoid `Any`, unchecked `cast`, and `type: ignore`. At an unavoidable dynamic boundary, isolate the
  uncertainty, narrow or validate the value, and explain any suppression where it is used.
- Use immutable defaults or `default_factory`; never share mutable default values between calls.

### Function contract

Every function or method MUST have one clear job that can be stated in its name and signature.

1. Name operations with a specific verb and object. Names such as `process`, `handle`, or `manage`
   need a precise subject or should be split into clearer operations.
2. Make inputs, outputs, effects, and failure behavior explicit. A caller should be able to tell
   whether a function mutates state, performs I/O, retries, or raises from its contract and name.
3. Keep one level of abstraction per function. Use guard clauses for invalid or terminal cases;
   extract a helper only when its name clarifies a meaningful step or gives a needed test seam.
4. Avoid boolean flag parameters that select unrelated behavior. Use distinct functions or a
   typed options object when the choices are genuinely one operation with explicit configuration.
5. Prefer a small number of cohesive arguments. If several arguments always travel together, use a
   typed request/configuration object. Do not introduce a wrapper solely to reduce a count.
6. Separate commands that change state from queries that return information when combining them
   would surprise callers. Do not return a success-looking sentinel when an operation failed.
7. Validate untrusted input at the boundary where it enters the package. Enforce domain invariants
   when constructing or changing domain values so invalid state cannot circulate internally.
8. Document public functions with a concise docstring describing purpose and non-obvious
   constraints, side effects, raised exceptions, and concurrency behavior. Do not restate the
   implementation line by line.

Do not enforce arbitrary line-count limits. A longer function is acceptable when its steps form one
cohesive operation; split it when separate decisions, effects, or failure handling obscure the
contract. Avoid clever one-liners, premature generalization, duplicate business rules, and
comments that compensate for unclear code.

### Types and classes

- Use `Protocol` for structural ports at package boundaries; use concrete classes for concrete
  behavior. Inject dependencies through constructors or function arguments rather than hidden
  globals.
- Use dataclasses or Pydantic models where they fit the layer. Keep transport/request schemas at
  external boundaries; keep domain rules independent of web and persistence frameworks.
- Value objects should be immutable and validate their invariants. Entities have stable identity;
  do not equate identity-bearing objects solely by all field values.
- Give each class one cohesive responsibility. Prefer composition over inheritance. Inheritance is
  for a real substitutable contract, not just code reuse.
- Keep module imports acyclic and module initialization free of network, database, or other
  operational side effects.

## 4. Public APIs

### Python package APIs

- Treat names exported from a package `__init__.py`, documented symbols, CLI flags, and generated
  project interfaces as public contracts.
- Export only stable, intentional symbols. Keep helpers private with a leading underscore unless
  callers have a concrete supported use case.
- Preserve signatures, defaults, return types, exception semantics, and behavior by default. A
  breaking change requires explicit authorization and a migration/deprecation plan.
- Deprecate before removal using the package's established `DeprecationWarning` pattern, with a
  useful replacement message and correct `stacklevel`.
- Document additions and changes in the owning package README/reference and relevant guides. Keep
  optional dependency imports lazy or boundary-local so base installations remain usable.

### HTTP APIs

FastAPI endpoints are adapters. They MUST validate and translate HTTP input, apply authentication
and authorization dependencies, call an application/domain operation, and map its result or
failure to HTTP. They MUST NOT become the only home of reusable business rules.

- Follow the owning application's configured prefix (`Settings.api_prefix`) and established
  versioning; do not add a version prefix globally without an API-wide decision.
- Prefer resource-oriented lowercase paths and HTTP method semantics. Use action paths only when
  the operation is a real command that does not fit resource CRUD, as in the existing authentication
  and workflow examples.
- Define typed request and response schemas for public or non-trivial endpoints. Bound strings,
  collections, uploads, pagination limits, and other attacker-controlled sizes.
- Use HTTP status codes according to outcome: distinguish authentication failure, authorization
  failure, missing resources, conflicts, validation failures, creation, and empty success. Do not
  return a success status with an embedded failure.
- Keep one response/error convention within an application. Do not impose a new envelope on an
  existing API without a compatibility plan. Never expose stack traces, SQL errors, secrets, or
  internal exception text to clients.
- Authenticate before authorizing. Check resource ownership and tenant scope on every operation,
  including reads and updates; a tenant identifier in a request is not proof of access.
- Add OpenAPI metadata and tests for success, invalid input, missing/invalid identity, denied access,
  not-found, and conflict cases that apply to the endpoint.
- Collection endpoints MUST have bounded pagination or another explicit result-size limit. Use the
  existing repository page/cursor abstractions where appropriate; define stable ordering and validate
  cursors and filters.

## 5. Errors, logging, and observability

- Raise meaningful package errors. Derive shared framework/application failures from the existing
  `ApyraError` hierarchy where appropriate; do not create overlapping exception trees.
- Catch the narrowest expected exception at the boundary that can recover or translate it. Preserve
  context with `raise ... from exc`. Do not swallow unexpected exceptions or return an empty result
  as a fallback for a failed operation.
- Map domain/application failures to transport-safe HTTP or CLI output only at the outer boundary.
  Keep internal exception details out of public responses.
- Use a module logger (`logging.getLogger(__name__)`) for diagnostics. Configure it once at the
  application composition root with the existing `apyra.observability.configure_logging` function.
  Do not call `print()` for operational diagnostics; reserve stdout for intentional CLI results,
  machine-readable output, and script reports.
- Log useful event context, not secrets or full sensitive payloads. Never log passwords, tokens,
  private keys, cookies, authorization headers, or raw credentials. Prefer bounded identifiers and
  structured context; avoid high-cardinality or personal values in metrics and spans.
- Do not add a dependency on `apyra-observability` to a lower-level distribution only to obtain a
  logger. Use Python's logger there; the application configures it through the existing package
  boundary.

## 6. Async work, resources, and persistence

- In `async` code, await asynchronous work and do not perform blocking network, filesystem, sleep,
  or database calls on the event loop. Use an async adapter or an appropriate thread boundary for
  unavoidable synchronous operations.
- Set explicit timeouts for external operations. Propagate cancellation; do not catch
  `BaseException` except for narrowly scoped cleanup that re-raises it.
- Acquire/release clients, sessions, tasks, and temporary resources with context managers or a
  guaranteed `finally` path. Do not leak unowned background tasks.
- Put transaction boundaries around one coherent unit of work. Ensure partial failure does not
  leave related state inconsistent. Do not commit from domain logic.
- Apply tenant and authorization scopes to every database operation; never rely on a later filter
  to hide a cross-tenant read.
- Use parameterized query APIs. Validate dynamic column names, sort keys, filters, and cursor input
  against explicit allowlists and constraints.
- Treat `create_all` as a controlled test/example convenience, not a production schema-upgrade
  mechanism. Schema changes for existing installs require a reviewed migration path, forward/backward
  compatibility assessment, and recovery plan.
- Test database semantics against the actual supported engine. SQLite or mocks do not prove
  PostgreSQL locking, concurrency, or transaction guarantees.

## 7. Messaging, retries, and background work

- State delivery guarantees precisely. Apyra Redis Streams consumers are at-least-once; duplicates
  are expected. Do not claim exactly-once behavior.
- Make side effects idempotent when retries or duplicate delivery are possible. Persist idempotency
  state at a durability level that matches the protected side effect.
- For database changes plus outbound messages, use the existing outbox pattern and one transaction
  where supported. Define when an item is claimed, acknowledged, retried, or dead-lettered.
- Retry only failures that may recover. Use bounded attempts, backoff, jitter where appropriate,
  timeouts, and a documented exhausted-message outcome. Do not retry a non-idempotent action blindly.
- Handle cancellation, duplicate delivery, worker crashes, lease/claim expiration, retry exhaustion,
  and partial success. Keep pending work recoverable until durable completion is recorded.
- Validate distributed guarantees with real database/broker integration tests; do not substitute
  mocks or in-memory stores for cross-process guarantees.

## 8. Security and privacy

- Treat every external value, webhook, file path, message, and persisted legacy record as untrusted.
  Validate type, length, format, range, ownership, and allowed values at the appropriate boundary.
- Fail closed for authentication, authorization, tenant ownership, CSRF, and secret validation.
  Authentication alone never grants access to a resource.
- Use approved password/token/crypto helpers; do not implement custom cryptography or weaken
  algorithms, validation, or security tests for convenience.
- Keep secrets in configuration providers, not source, fixtures, diagnostics, screenshots, or test
  output. Use dummy test secrets only in tests.
- Test denial paths, cross-tenant access, malformed input, replay/idempotency, and sensitive-data
  redaction when relevant. Security-sensitive changes require negative tests.

## 9. Tests and verification

Tests MUST prove observable behavior, not merely imports or implementation details.

- Put package tests under the owning `packages/<package>/tests/`; use `tests/integration/` for
  cross-package contracts and repository-level gates.
- Name tests after scenario and expected behavior. Cover a successful path and relevant invalid,
  boundary, authorization, failure, retry, cleanup, and compatibility paths.
- Prefer deterministic tests with controlled clocks, generated temporary paths, and isolated state.
  Clean up clients, tasks, temporary files, and environment changes.
- Unit-test pure/domain/application behavior without external services. Use contract tests for
  adapters and real Redis/PostgreSQL tests when behavior depends on those services.
- A skipped service test is unverified; report it. Do not mark a gate passed by replacing its real
  service with a mock or weaker database.
- Do not use meaningless assertions, weaken assertions to make a test pass, or hide a failing test
  behind a broad skip.
- For source changes run focused tests, then `just check`. For documentation changes run
  `just docs-check`. For distribution, dependency, or generator changes, also run the applicable
  build/install/release validation commands from `AGENTS.md`.
- Report the exact commands run and distinguish local checks from hosted CI and production evidence.

## 10. Dependencies, configuration, and generated projects

- Declare direct dependencies in the owning distribution's `pyproject.toml`; use extras for
  optional backends and integrations. Update `uv.lock` when dependency resolution changes.
- Inspect the workspace manifests and package export/install tests before changing packaging. A
  package must build and install independently.
- Load settings through the owning configuration model. Do not open network/database connections
  at import time or read environment variables deep inside domain logic.
- Generated code is a public developer experience contract. It MUST use supported imports and
  defaults, install and start, handle existing files safely, and pass its relevant lint, type, test,
  and smoke checks.
- Keep diagnostic commands read-only by default. For generators, preserve dry-run behavior and do
  not overwrite existing user files without an explicit safe mechanism.

## 11. Documentation, review, and completion

- Update the owning package README, API reference/docstrings, guide, migration note, and navigation
  for public behavior as applicable. Examples must match supported APIs and run under their stated
  setup.
- Keep comments for rationale, invariants, security constraints, and non-obvious trade-offs. Remove
  stale comments and commented-out code; version control holds history.
- Before completion, review the diff for behavior, architecture, security, typing, error handling,
  compatibility, performance, tests, and unrelated changes.
- A task is complete only when acceptance behavior exists, required tests and checks were executed,
  public contracts and docs are handled, and unresolved blockers are reported accurately.

## Quick review checklist

- [ ] Correct package owns the code; imports and dependencies obey declared boundaries.
- [ ] Function and API contracts are typed, validated, documented, and backward compatible.
- [ ] Authorization, tenant scope, error mapping, and sensitive-data handling are explicit.
- [ ] Async resources, transactions, retries, idempotency, and cancellation are safe where relevant.
- [ ] Tests cover user-visible success and failure behavior; real services verify real guarantees.
- [ ] Package exports, extras, generated projects, docs, and migration notes are updated where needed.
- [ ] Devcontainer quality gates and `git diff --check` pass; skipped checks are disclosed.
