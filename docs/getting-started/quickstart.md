# Five-minute quickstart

This path runs from a synced source checkout. It does not require published Apyra packages.

## 1. Generate a minimal API

From the repository root:

```bash
cd /tmp
uv run --project /path/to/apyra apyra new apyra-quickstart
```

Replace `/path/to/apyra` with the actual path to your cloned repository. The command refuses to overwrite an existing directory; choose a new name for another run.

The generator creates `/tmp/apyra-quickstart/main.py` with an `/api/health` route.

## 2. Start it

```bash
cd /tmp/apyra-quickstart
uv run uvicorn main:app --host 0.0.0.0 --port 5000
```

Open <http://localhost:5000/docs> for interactive OpenAPI documentation, or verify health:

```bash
curl --fail http://localhost:5000/api/health
# {"status":"ok"}
```

## 3. Add a protected endpoint

Add this route to `main.py` and import `Depends` plus `get_current_token`:

```python
from fastapi import APIRouter, Depends

from apyra.fastapi import get_current_token


@router.get("/me")
async def me(
    token: dict[str, object] = Depends(get_current_token),
) -> dict[str, object]:
    return {"subject": token["sub"]}
```

Configure `app.state.auth_settings` with an `AuthSettings` instance for your issuer before accepting
traffic. Use JWKS for a production identity provider. The [authentication guide](../guides/authentication.md)
shows both the production boundary and local HS256 testing; an unconfigured protected request fails
closed rather than accepting an unsigned token.

## 4. Test the application

```python
from fastapi.testclient import TestClient

from main import app


def test_health() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run it with the workspace environment:

```bash
cd /tmp/apyra-quickstart
uv run --project /path/to/apyra pytest -q
```

The generated project declares the future package dependency for independent installation. During
source validation, `--project /path/to/apyra` intentionally uses the synced workspace instead.

## Maintainer proof: clean built artifacts

The release gate also proves both CLI templates from built artifacts, without importing the workspace
source tree. It builds all 20 distributions into a fresh directory, installs every wheel and sdist in
disposable Python 3.12 environments, then generates and exercises the minimal and cookie-auth apps:

```bash
release_dist=$(mktemp -d /tmp/apyra-release-dist.XXXXXX)
for package_name in core fastapi storage db auth cache ai observability email channels \
  i18n events security tasks cli application domain messaging workflow; do
  uv build --package apyra-$package_name --out-dir $release_dist
done
uv build --package apyra --out-dir $release_dist
uv run --no-project --python 3.12 scripts/validate_release.py --dist $release_dist
```

Success ends with:

```text
QUICKSTART VALIDATION OK
RELEASE VALIDATION OK
```

The cookie-auth check sends a real signed HS256 access token through Apyra's JWT validator, obtains a
CSRF token bound to the access-token cookie, and completes the protected write. HMAC is confined to
this disposable local validation; production guidance remains asymmetric JWKS.

This command validates local artifacts. It does not publish them or prove that an external package
index serves them.

## Optional: Devcontainer

If you prefer a reproducible, isolated development environment, you can use the optional
Devcontainer configuration in [`.devcontainer/`](../../.devcontainer/):

```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . uv run --project /workspaces/apyra apyra new apyra-quickstart
```