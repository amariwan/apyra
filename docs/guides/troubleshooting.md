# Troubleshooting

## `ModuleNotFoundError: apyra.<package>`

Sync the relevant workspace package or install its distribution. The `apyra` metapackage does not
place all optional packages in every environment. Never add `apyra/__init__.py`; the namespace is
implicit by design.

## Protected routes return 401

Check the configured issuer, audience, algorithms, key source, expiry, and token-type requirements.
Do not disable validation to make a token pass. Compare configuration with the
[authentication guide](authentication.md).

## Integration tests are skipped

Read the skip reason. Start PostgreSQL or Redis locally or via Docker Compose and rerun the exact
marked test. A skipped test is not evidence that the integration works.

## Documentation build fails

```bash
just docs-check
```

Strict mode reports the first missing navigation target, unresolved internal link, duplicate anchor,
or API import problem. Fix the source or public import boundary; do not disable strict mode.

## Generated project cannot resolve Apyra

The repository generator declares release dependencies. If packages are not published in your index,
use the [source-checkout quickstart](../getting-started/quickstart.md) or locally built wheels. Do not
silently fall back to unrelated packages with the same name.
