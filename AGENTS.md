# AGENTS.md

## 1. Project Identity

**Project:** Apyra
**Repository:** https://github.com/amariwan/apyra
**Language:** Python >= 3.12
**Package Manager:** uv
**Architecture:** Modular Enterprise Backend Framework
**Repository Structure:** uv workspace monorepo

Apyra aims to become a world-class, production-grade Python enterprise backend framework.

Our engineering priorities are:

1. Developer experience
2. Clean architecture
3. Security by default
4. Reliability and resilience
5. Production observability
6. Type safety
7. Performance
8. Backward compatibility
9. Excellent documentation
10. Reproducible and trustworthy releases

Every change must improve or preserve these qualities.

Do not introduce complexity without a clear architectural or user-facing benefit.

---

## 2. Repository Architecture

Apyra consists of independently publishable Python distributions under `packages/`.

Discover the actual package inventory from the repository. Never rely on a hard-coded package count.

The project uses **PEP 420 implicit namespace packages**.

Rules:

- Never create `apyra/__init__.py`.
- Each concrete subpackage, such as `apyra.core`, owns its own `__init__.py`.
- Preserve independent package publication.
- Keep package dependencies explicit.
- Avoid circular dependencies.
- Avoid unnecessary shared global state.
- Do not bypass established architectural boundaries.

### Dependency Direction

Recommended dependency direction:

```text
Core
  ↓
Domain
  ↓
Application
  ↓
Infrastructure / Adapters
  ↓
API / Application Composition
```

This represents architectural dependency rules, not a requirement that every package depend on the package immediately above it.

Mandatory constraints:

- `apyra-core` must remain independent of FastAPI and infrastructure packages.
- Domain code must not depend on HTTP frameworks, databases, brokers, or application-layer implementations.
- Application contracts must not require concrete infrastructure adapters.
- Infrastructure should implement established contracts.
- Optional integrations must remain optional.
- Public APIs must remain stable unless a breaking change is explicitly authorized.

Prefer dependency inversion and composition over tight coupling.

---

## 3. Development Environment

## Development Environment — Devcontainer Required

- Always use the Devcontainer for local development, testing, builds, and dependency management.
- Keep macOS clean: no project-specific Python packages, virtual environments, or development services installed on the host.
- Run commands via `devcontainer exec --workspace-folder . <command>`.
- If already inside the Devcontainer, execute commands directly.
- Use Docker volumes for `.venv`, caches, PostgreSQL, and Redis.
- Never fall back to host Python or install dependencies globally.
- CI/CD environments are independent and do not require a Devcontainer.
- If the Devcontainer fails, fix it instead of bypassing it.

### CI and Other Execution Environments

Hosted CI, release workflows, and other isolated environments may use their own configured Python environments.

The Devcontainer requirement applies to local development and testing; it does not override CI workflow configurations.

Never claim an environment has been verified unless commands actually ran successfully in that environment.

---

## 4. Mandatory Engineering Workflow

Every implementation task must follow this sequence:

**USE SKILLS → CODE REVIEW → CLEAN CODE → IMPLEMENT → TEST → CODE REVIEW → VERIFY → NEXT GOAL**

### Step 1 — USE SKILLS

Before modifying code:

1. Read this `AGENTS.md`.
2. Inspect relevant repository files and documentation.
3. Discover available skills.
4. Read and follow relevant skill instructions.
5. Identify applicable coding, testing, security, and architectural conventions.

Use available skills for:

- Clean Code
- Code Review
- Architecture Review
- Security Review
- Testing
- Documentation
- Performance Optimization

If a relevant skill is unavailable, continue using the repository's established engineering standards.

Never claim to have used a skill that was not available or executed.

### Step 2 — INITIAL CODE REVIEW

Before implementation:

- Understand the existing behavior.
- Inspect related modules and tests.
- Identify existing abstractions.
- Check dependency boundaries.
- Identify compatibility risks.
- Search for reusable components.
- Check whether the feature already exists.
- Examine relevant documentation.

Do not duplicate existing functionality.

### Step 3 — CLEAN CODE DESIGN

Design the smallest maintainable solution.

Follow:

- SOLID where useful
- DRY without premature abstraction
- KISS
- Explicit dependencies
- Separation of concerns
- Type-safe interfaces
- Small, focused functions
- Clear naming
- Minimal public API surface

Avoid:

- God classes
- Hidden side effects
- Circular imports
- Unnecessary inheritance
- Broad exception swallowing
- Unexplained `type: ignore`
- Hard-coded credentials
- Dead code
- Premature frameworks
- Needless dependencies

Do not refactor unrelated code unless required for correctness.

### Step 4 — IMPLEMENTATION

Implement the agreed functionality completely.

Requirements:

- Follow existing architecture.
- Preserve backward compatibility by default.
- Include meaningful error handling.
- Validate external input.
- Keep secrets out of logs.
- Prefer deterministic behavior.
- Handle relevant failure scenarios.
- Document new public APIs.
- Keep optional dependencies optional.

Generated code must be executable, maintainable, and consistent with project standards.

Never overwrite existing user files without explicit authorization or an established safe overwrite mechanism.

### Step 5 — TESTING

Write tests that validate real behavior.

Include where relevant:

- Unit tests
- Integration tests
- Negative tests
- Security tests
- Regression tests
- Boundary-condition tests
- Failure and recovery tests
- Generated-project smoke tests
- Compatibility tests

Tests must not merely assert that imports succeed when functional behavior needs verification.

Avoid meaningless assertions such as `assert True`.

Do not weaken tests to make them pass.

Do not silently skip mandatory tests.

### Step 6 — SECOND CODE REVIEW

After implementation, review the actual changes.

Check:

1. Correctness
2. Architecture
3. Security
4. Readability
5. Maintainability
6. Performance implications
7. Backward compatibility
8. Error handling
9. Test coverage
10. Documentation

Fix identified issues before completing the task.

### Step 7 — VERIFY

Run the relevant quality gates.

Never report success for commands that were not executed.

### Step 8 — NEXT GOAL

Once the current goal is verified:

1. Update the development progress document.
2. Identify remaining requirements.
3. Select the next highest-priority actionable task.
4. Continue implementation when within the authorized scope.

Do not request confirmation after every small step.

Stop when additional permissions, external publication, destructive actions, or essential user decisions are required.

---

## 5. Quality Gates

### Dependency Synchronization

```bash
uv sync --all-packages --all-extras
```

### Lint

```bash
uv run ruff check .
```

### Formatting Verification

```bash
uv run ruff format --check .
```

### Type Checking

```bash
uv run mypy
uv run pyright
```

### Tests

```bash
uv run pytest
```

### Full Validation

```bash
just check
```

### Release Validation

```bash
uv run python scripts/validate_release.py
```

Use existing documented commands when their invocation differs.

Check available Justfile recipes before assuming a command exists.

When preparing releases, also validate:

- Wheel and sdist builds
- Independent installation
- Public imports
- Dependency resolution
- Generated-project compatibility
- Documentation builds
- Security audits
- Package metadata

A change is not complete simply because Ruff passes.

---

## 6. Code Quality Standards

### Python

- Target Python >= 3.12.
- Use modern Python typing.
- Prefer explicit return types.
- Prefer precise types over `Any`.
- Use `Protocol` for suitable structural contracts.
- Use dataclasses or Pydantic models where appropriate.
- Prefer composition over inheritance.
- Keep public interfaces minimal.

### Formatting

Follow the repository configuration.

Current conventions include:

- Ruff line length: 100
- Python target: py312
- Strict mypy and Pyright checks

Do not duplicate tool configuration unnecessarily.

### Error Handling

- Raise meaningful exceptions.
- Preserve exception context.
- Avoid catching `Exception` without a clear reason.
- Do not hide failed operations.
- Never leak credentials through exceptions or logs.

### Async Programming

- Avoid blocking operations in async functions.
- Manage cancellation correctly.
- Close resources reliably.
- Use explicit timeouts where appropriate.
- Avoid unmanaged background tasks.

---

## 7. Security Requirements

Security is mandatory, not optional polish.

For relevant changes, consider:

- Authentication
- Authorization
- Tenant isolation
- Input validation
- Secrets management
- Rate limiting
- Secure defaults
- Audit logging
- Dependency vulnerabilities
- Injection vulnerabilities
- Sensitive-data exposure
- Session and token handling

### Mandatory Security Rules

- Never hard-code secrets.
- Never log passwords, access tokens, or private keys.
- Never bypass authorization checks for convenience.
- Never disable security checks to satisfy tests.
- Prefer fail-closed behavior for sensitive operations.
- Test that cross-tenant access is denied.
- Treat external payloads as untrusted.

For security-sensitive changes, include negative tests and document relevant security assumptions.

---

## 8. Reliability and Distributed Systems

Apyra supports enterprise workloads involving messaging, persistence, workflows, and background processing.

When modifying these systems, consider:

- Transaction boundaries
- Idempotency
- Duplicate message delivery
- Retry exhaustion
- Dead-letter handling
- Crash recovery
- Lease expiration
- Concurrent workers
- Resource cleanup
- Partial failures

Never promise exactly-once processing unless the complete guarantee is established and verified.

Prefer explicit, documented delivery semantics.

Integration tests should use real infrastructure when guarantees depend on database or broker behavior.

Mock-only tests do not establish distributed-system guarantees.

---

## 9. Developer Experience Standards

Developer experience is a first-class product feature.

CLI and project-generation changes must be:

- Predictable
- Discoverable
- Safe
- Consistent
- Well documented
- Automation-friendly

### CLI Requirements

- Provide useful help messages.
- Give actionable errors.
- Support non-interactive usage where appropriate.
- Prefer structured output for automation.
- Keep diagnostic commands read-only by default.
- Redact sensitive configuration.

### Code Generation

Generated projects must:

- Install successfully.
- Start successfully.
- Pass linting.
- Pass type checking.
- Pass tests.
- Follow Apyra architecture.
- Avoid unnecessary dependencies.

Generators must safely handle existing files.

Provide dry-run support where practical.

Do not generate duplicate registrations, imports, routes, or configuration entries.

---

## 10. Documentation Requirements

Every significant feature should include:

- Purpose
- Installation
- Quick-start example
- Configuration
- Public API
- Error behavior
- Integration guidance
- Security considerations where relevant
- Compatibility information

Examples must use real, supported APIs.

Never document hypothetical behavior as already implemented.

Update package READMEs and the documentation website when public behavior changes.

---

## 11. Performance Requirements

Performance work must be evidence-based.

Do not claim Apyra is faster than FastAPI or competing frameworks without reproducible benchmarks.

For benchmark changes, record:

- Hardware
- Python version
- Dependency versions
- Concurrency
- Request volume
- Warm-up conditions
- Throughput
- p50/p95/p99 latency
- Memory usage
- Comparison baseline

Prioritize correctness and maintainability before micro-optimizations.

---

## 12. Package Integration Checklist

When adding or modifying a distribution, inspect all relevant integration surfaces:

- Workspace configuration
- Package `pyproject.toml`
- Dependency declarations
- Optional extras
- uv lockfile
- mypy configuration
- Pyright configuration
- Ruff configuration
- CI workflows
- Justfile
- Build and release scripts
- Metapackage integration
- Architecture tests
- Public API exports
- Package README
- Documentation navigation
- Import smoke tests

Do not hard-code package counts in tests or documentation when they can be discovered reliably.

New distributions must be independently buildable and installable.

---

## 13. Enterprise Development Roadmap

Apyra has ten strategic development goals.

### G1 — Apyra Project Builder

CLI and web-based generation with configurable architecture, database, authentication, caching, messaging, observability, and deployment integrations.

### G2 — Developer CLI

Resource, module, service, use-case, test, and migration generation with safe dry-runs and existing-code awareness.

### G3 — Documentation Platform

Versioned documentation, API reference, quick-start guides, architecture guides, migration instructions, and enterprise examples.

### G4 — Apyra Doctor

Read-only diagnostics for dependencies, configuration, database connectivity, migrations, secrets, and deployment settings.

### G5 — Enterprise Security Profiles

Validated configurations for API-only, browser-session, and multi-tenant SaaS applications.

### G6 — Production Diagnostics

Readiness checks, tracing, metrics, OpenTelemetry integration, worker diagnostics, and workflow observability.

### G7 — Golden-Path Templates

Fully tested:

1. Minimal API
2. Modular Monolith
3. Distributed Application

### G8 — Public Performance Lab

Reproducible benchmarks with published methodology and measurable results.

### G9 — Verified Releases

Trusted publishing, artifact verification, SBOMs, provenance, and security policies.

### G10 — Open-Source Ecosystem

Governance, contributor documentation, community support, integration examples, and a curated adapter ecosystem.

These goals are ongoing engineering objectives.

Do not mark a goal complete without verifying its acceptance criteria.

---

## 14. Autonomous Development Rules

Agents should work autonomously within the authorized scope.

### Required Behavior

1. Read the current roadmap and progress report.
2. Identify the highest-priority incomplete requirement.
3. Break it into verifiable deliverables.
4. Follow the mandatory engineering workflow.
5. Implement and validate the deliverable.
6. Record actual results.
7. Continue to the next actionable requirement.

### Progress Tracking

Use:

`docs/roadmap/enterprise-development-progress.md`

Record:

- Current phase
- Current goal
- Completed deliverables
- Evidence and validation results
- Remaining tasks
- Risks and blockers
- Next goal

Do not reset the roadmap after an interrupted session.

Resume from verified repository state.

### Completion Rules

A goal is complete only when:

- Required functionality exists.
- Relevant tests pass.
- Architectural constraints hold.
- Documentation is updated.
- No unresolved critical issues remain.
- Required integration gates have been verified.

Partial completion must be reported honestly.

---

## 15. Git and Repository Safety

Preserve existing user work.

Before editing, inspect relevant files and repository status.

Never assume unrelated modifications are disposable.

### Prohibited Without Explicit Authorization

- `git reset --hard`
- `git clean`
- Destructive checkout operations
- Force push
- History rewriting
- Deleting unrelated files
- Publishing packages
- Deploying production systems
- Creating releases
- Pushing commits
- Committing changes

Do not automatically commit or push.

Do not modify remote repository state without authorization.

Do not expose secrets or sensitive environment values in reports.

---

## 16. Handling Blockers

When a required service, dependency, tool, or permission is unavailable:

1. Identify the exact blocker.
2. Run safe, relevant checks.
3. Complete independent work when possible.
4. Document what remains unverified.
5. Do not claim a mandatory gate passed.
6. Request authorization only when genuinely required.

Do not replace required integration verification with mocks and declare the goal complete.

---

## 17. Final Reporting Standard

At the end of a completed development iteration, provide a concise report:

```text
APYRA ENTERPRISE DEVELOPMENT REPORT

Phase:
Goal:
Status: COMPLETE / PARTIAL / BLOCKED

Implemented:
- ...

Skills used:
- ...

Code review:
- Findings and fixes

Clean code:
- Improvements

Validation:
- Ruff:
- Format:
- Mypy:
- Pyright:
- Pytest:
- Integration tests:
- Release validation:

Compatibility:
- ...

Security:
- ...

Remaining risks:
- ...

Next goal:
- ...
```

Report only verified results.

Do not invent passing tests, coverage values, security findings, or benchmark measurements.

---

## 18. Permanent Engineering Principle

**Every implementation must make Apyra more professional, maintainable, secure, reliable, and pleasant to use.**

The mandatory sequence is:

**USE SKILLS → CODE REVIEW → CLEAN CODE → IMPLEMENT → TEST → CODE REVIEW → VERIFY → NEXT GOAL**

Never sacrifice correctness for speed.

Never sacrifice security for convenience.

Never sacrifice maintainability for unnecessary features.

Never claim production readiness without evidence.

Continue the enterprise roadmap autonomously within the authorized scope until its acceptance criteria are satisfied or a genuine blocker requires user input.

**Build Apyra to a standard that experienced enterprise engineers would confidently adopt, maintain, and recommend.**
