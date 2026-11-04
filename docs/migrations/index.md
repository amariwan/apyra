# Migration guides

No stable Apyra release has been declared by the current source checkout, so there is no released
version-to-version migration guide yet.

For each compatibility-affecting release, this section records:

- the old and new public behavior;
- the first version containing the change;
- deprecation warnings and removal version;
- mechanical code/configuration changes;
- data migration and rollback requirements;
- verification commands.

Until then, use the package changelog and compare the exact release artifacts you intend to install.
Do not infer compatibility from the workspace version alone: Apyra consists of independently
published distributions.

The [`0.1.0 release-hardening schema upgrade`](0.1.0-release-hardening.md) documents the additive
database changes required when upgrading tables created before the P3–P7 hardening work.

Potentially breaking changes require an additive alternative or an explicit migration plan before
release. See [Changelog](../project/changelog.md) and [Release validation](../release/validation.md).
