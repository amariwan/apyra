# Apyra — Open-Source Growth Plan

> Status: public repository, early-stage release preparation. PyPI availability,
> current stars, and releases must be verified before any launch announcement.
> The numerical scores and audit below are a historical planning baseline, **not**
> a continuously updated assessment. Apyra now has auth, DB, storage, cache, and
> events examples, community files, and a corrected `just test-all` recipe.

## 1. Executive summary

Apyra is a modular, async-first Python framework for building FastAPI applications.
It ships 16 independently publishable packages under a PEP 420 namespace
(`apyra.*`), with a strict rule that `apyra-core` never depends on FastAPI or any
infrastructure package. The codebase has solid engineering hygiene: ruff + mypy +
pyright + pytest in CI across Python 3.12/3.13, a build/install smoke test, and
release automation to PyPI.

What is missing for adoption is **discoverability and onboarding**: a thin README,
a missing published docs site, unclear package-publication status, and opportunities
for clearer API references and example-driven tutorials. The biggest lever is making the first
5 minutes compelling and verifiable.

## 2. Repository maturity assessment

| Area | State | Notes |
|---|---|---|
| Source code | Mature-ish | 16 packages, async-first, typed |
| Tests | Present | 69 tests, pytest-asyncio auto |
| Lint/Typecheck | Strong | ruff, strict mypy on configured packages, pyright (basic mode) |
| CI | Good | quality + build + install jobs, matrix 3.12/3.13 |
| Release | Manual | `workflow_dispatch`, PyPI trusted publishing |
| Docs | Weak | README 69 lines, 1 architecture doc |
| Examples | Expanded | minimal, auth, database, storage, cache, and events demos |
| Community files | Now added | CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, templates |
| Published packages | None | v0.1.0, no PyPI release yet |
| GitHub presence | Public | https://github.com/amariwan/apyra |

## 3. Scores (0–100)

### Developer experience: 62/100
Criteria: install simplicity (8/15 — uv only documented, no pip fallback shown),
quickstart correctness (10/15 — example runs but README command was wrong, now fixed),
example completeness (6/15 — single minimal example), error clarity (10/15 — typed
errors exist), env clarity (12/15 — pydantic-settings documented in code), API
consistency (16/25 — factory-based, explicit). Improvements: pip install path,
more examples, API reference.

### Discoverability: 25/100
Criteria: README hook (5/20), topics/metadata (0/15 — no GitHub repo yet),
package metadata (10/20 — descriptions present but thin), social preview (0/10),
docs SEO (0/10), example discoverability (5/15), community channels (5/10).
Improvements: rewrite README (done), add topics, publish to PyPI, docs site.

### Documentation quality: 35/100
Criteria: README completeness (12/25), architecture doc (8/15), API reference (0/20),
package READMEs (5/15 — one-liners), examples (5/15), changelog (5/10 — exists).
Improvements: API docs, per-package READMEs, tutorials.

### Community readiness: 55/100 (was ~20 before this change)
Criteria: CONTRIBUTING (12/15), CODE_OF_CONDUCT (12/15), SECURITY (10/15),
issue templates (12/15), PR template (9/15), discussions (0/10 — not configured),
good-first-issue labelling (0/5 — none labelled yet), responsiveness (0/10 — no
maintainer history). Improvements: label issues, enable Discussions, maintainer SLA.

## 4. Top 15 prioritized improvements

1. Publish packages to PyPI (highest impact on adoption). Effort: M. Deps: versioning.
2. Rewrite README with clear value prop + verified quickstart. Effort: S. Done.
3. Add more runnable examples (auth, db, storage, cache, events, tasks). Effort: M.
4. Per-package READMEs with real usage. Effort: M.
5. API reference (mkdocs or sphinx). Effort: L.
6. Community files + templates. Effort: S. Done.
7. Keep the complete `just check` quality gate working. Effort: S. Done.
8. Enable GitHub Discussions + labels (good first issue, help wanted). Effort: S (manual).
9. Add a docs site (mkdocs-material). Effort: L.
10. Social preview image + repository description/topics. Effort: S (manual).
11. Integration tests across package boundaries. Effort: M.
12. Versioning + CHANGELOG automation. Effort: M.
13. Demo GIF / screenshot in README. Effort: M.
14. Comparison table vs FastAPI/Litestar/Django. Effort: S.
15. Contributor onboarding guide. Effort: S.

## 5. Competitive positioning

Verified competitors (public, well-known): FastAPI, Litestar, Starlette, Django +
Django REST Framework, Flask. These are frameworks; Apyra is a **modular
infrastructure layer on top of FastAPI**, not a competing web framework. That is
the honest differentiation: Apyra does not replace FastAPI's routing/ASGI core; it
provides composable infra (settings, db repos, auth, storage, cache, events, tasks)
that teams otherwise assemble ad hoc.

Hypotheses (not verified): teams adopting FastAPI repeatedly rebuild the same infra
glue; a modular, independently-versioned package set reduces that. This should be
validated with user interviews before claiming.

Positioning statement: *"Apyra is the modular backend infrastructure layer for
FastAPI — install only what you need, compose explicitly, ship faster."*

## 6. GitHub metadata suggestions (manual)

Repository description:
> Modular Python framework for building FastAPI applications with explicit, composable infrastructure. Async-first, independently publishable packages.

Topics: `python`, `fastapi`, `asyncio`, `pydantic`, `modular`, `framework`,
`uv`, `sqlalchemy`, `jwt`, `oauth2`, `redis`, `openai`, `observability`,
`background-tasks`, `i18n`.

## 7. 90-day roadmap

### Days 1–14: Foundation
- Publish v0.1.0 to PyPI (core + fastapi first). Priority: P0, Impact: high, Effort: M.
- Add pip-based quickstart. Priority: P1, Impact: medium, Effort: S.
- Validate and document the existing auth+DB examples. Priority: P1, Impact: high, Effort: M.
- Keep `just check` aligned with CI. Priority: P2, Impact: low, Effort: S. Done.
- Add demo GIF. Priority: P2, Impact: medium, Effort: M.

### Days 15–30: Initial distribution
- Publish launch article (Dev.to + personal blog). Priority: P1, Impact: high, Effort: M.
- Submit to Awesome Python / Awesome FastAPI lists. Priority: P1, Impact: medium, Effort: S.
- Post Show HN. Priority: P1, Impact: high, Effort: S.
- Collect feedback via Discussions. Priority: P1, Impact: medium, Effort: S.

### Days 31–60: Community & adoption
- Per-package READMEs + API reference. Priority: P1, Impact: high, Effort: L.
- Integration tests. Priority: P2, Impact: medium, Effort: M.
- Release v0.2.0 with feedback-driven changes. Priority: P1, Impact: high, Effort: M.
- Label 5 good-first-issues. Priority: P2, Impact: medium, Effort: S.

### Days 61–90: Sustainable growth
- Docs site (mkdocs-material). Priority: P2, Impact: high, Effort: L.
- Case study / deep-dive article. Priority: P2, Impact: medium, Effort: M.
- Partner with complementary projects. Priority: P3, Impact: medium, Effort: M.
- Evaluate growth experiments. Priority: P2, Impact: medium, Effort: S.

## 8. KPI framework

Available from GitHub (after publishing): stars, forks, views, unique visitors,
clones, contributors, issues, PRs. From PyPI: download counts. From docs site:
page views (if added). Manual: community post engagement, feedback themes.

Baseline: record actual public GitHub stars, traffic, and package downloads immediately before launch; do not assume zero.

Hypotheses to test:
- H1: A clear 5-minute quickstart increases star conversion from README views.
- H2: Publishing to PyPI is a prerequisite for adoption; pre-PyPI, only dev users.
- H3: More runnable examples reduce "how do I use this" issues.

## 9. Launch content (drafts)

### Show HN (concept)
Title: "Show HN: Apyra – modular backend infrastructure layer for FastAPI"
Body: focus on the problem (teams rebuild infra glue), the modular approach,
verified quickstart, and honest status (early, v0.1.0). Invite feedback.

### Dev.to tutorial (outline)
"How to build a FastAPI app with Apyra: settings, db, auth, cache in 30 minutes"
with a runnable example per section.

### X/Twitter (concept)
Short thread: "I kept rebuilding the same FastAPI infra in every project. So I
extracted it into modular packages. Here's the 5-min quickstart."

## 10. Implementation backlog (prioritized)

| # | Task | Priority | Effort | Status |
|---|---|---|---|---|
| 1 | README rewrite | P0 | S | Done |
| 2 | Community files + templates | P0 | S | Done |
| 3 | Fix `just check` (empty test-all) | P1 | S | Done |
| 4 | Publish to PyPI | P0 | M | Pending (manual) |
| 5 | More examples | P1 | M | Auth/DB/storage/cache/events present; tasks pending |
| 6 | Per-package READMEs | P1 | M | Pending |
| 7 | API reference / docs site | P2 | L | Pending |
| 8 | GitHub metadata + topics | P1 | S | Manual |
| 9 | Social preview image | P2 | M | Pending |
| 10 | Good-first-issue labels | P2 | S | Manual |
| 11 | Integration tests | P2 | M | Pending |
| 12 | Comparison article | P3 | S | Pending |

## Non-negotiables

No bought stars, no fake accounts, no Trending manipulation, no exaggerated
claims, no spam. Every claim in README/docs must be verifiable against the repo.
