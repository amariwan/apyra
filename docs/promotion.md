# Organic project discovery

Stars follow useful exposure; no launch plan can guarantee them. The aim is to reach developers
who build Python APIs, help them evaluate Apyra quickly, and earn stars from people who find it
useful. Do not buy stars, use exchanges, or ask for drive-by stars without genuine interest.

## Current launch readiness

Checked 2026-10-30; recheck before launch:

- The public repository has 17 relevant topics, a MIT license, CI, a v0.1.0 GitHub release, and
  a source quick start. GitHub showed 0 stars when checked.
- `apyra` was not available on PyPI when checked. The README now says so and points to a runnable
  source example. Treat package publication as a prerequisite before inviting users to install
  from PyPI.
- Review the GitHub About description before promotion: it currently says “production-ready,”
  while the README roadmap still lists API stabilization and PyPI publication.
- Add a clear 1280×640 social preview image in repository settings. Show the product and its
  modular install/use case, not a star-count claim.

## Two-week promotion plan

1. **Make the first try work.** Publish the packages through the existing release workflow, verify
   `uv add apyra-core apyra-fastapi` in a clean project, and keep the README install instructions
   consistent with the release. If release is not ready, promote the runnable source example and
   say that clearly.
2. **Show one concrete use case.** Record a short terminal demo: install the minimal pieces, wire
   a FastAPI app, and open `/docs`. Include the code and a link to the example so readers can
   reproduce it.
3. **Share where Python API developers already discuss tooling.** Start with one suitable
   community or launch channel, explain the problem Apyra solves, disclose that you maintain it,
   and ask for technical feedback. Follow each community’s current self-promotion rules. Join the
   discussion and answer questions; do not cross-post the same pitch everywhere on the same day.
4. **Turn feedback into the next update.** Fix onboarding gaps, publish a useful example or
   release note, then share what changed with the people who gave feedback. Track referral visits,
   stars, forks, issues, and package installs where available; prioritize real use and feedback
   over a star target.

## Ready-to-edit launch drafts

### Hacker News / technical forum

**Title:** Show HN: Apyra — compose FastAPI infrastructure from separately installable Python packages

**Post:** I built Apyra to try a more modular way to assemble FastAPI services: a shared `apyra.*`
namespace with separate packages for core, database, auth, storage, cache, and other common
infrastructure. The repository includes a runnable example. I maintain the project and would value
feedback on whether this packaging model is useful and where the onboarding is unclear:
https://github.com/amariwan/apyra

### Short social post

I built Apyra for Python teams that want to compose FastAPI infrastructure from smaller packages
instead of adopting one all-in-one framework. It is MIT-licensed, async-first, and includes a
runnable example. I would value feedback from people building APIs:
https://github.com/amariwan/apyra

If it looks useful to you, a ⭐ helps other Python developers find it.

## References

- [GitHub: 5 tips for promoting your open source project](https://github.blog/open-source/maintainers/5-tips-for-promoting-your-open-source-project/)
- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
