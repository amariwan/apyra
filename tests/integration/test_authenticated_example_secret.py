from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "authenticated-api" / "main.py"


@pytest.mark.parametrize("secret", [None, "short"])
def test_authenticated_example_requires_a_32_byte_secret(secret: str | None) -> None:
    environment = os.environ.copy()
    environment.pop("APYRA_EXAMPLE_JWT_SECRET", None)
    if secret is not None:
        environment["APYRA_EXAMPLE_JWT_SECRET"] = secret

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import runpy, sys; runpy.run_path(sys.argv[1])", str(EXAMPLE)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert "APYRA_EXAMPLE_JWT_SECRET" in result.stderr


def test_authenticated_example_runs_with_configured_secret() -> None:
    environment = os.environ.copy()
    environment["APYRA_EXAMPLE_JWT_SECRET"] = secrets.token_hex(32)
    smoke = """
import os
import runpy
import sys
import time
import jwt
from fastapi.testclient import TestClient
app = runpy.run_path(sys.argv[1])["app"]
with TestClient(app) as client:
    login = client.post("/api/login", json={"username": "alice", "password": "secret"})
    token = login.json()["access_token"]
    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    untyped_token = jwt.encode(
        {"sub": "alice", "iat": int(time.time()), "exp": int(time.time()) + 600,
         "iss": "apyra-example", "aud": "apyra-example-api"},
        os.environ["APYRA_EXAMPLE_JWT_SECRET"],
        algorithm="HS256",
    )
    untyped_response = client.get(
        "/api/me", headers={"Authorization": f"Bearer {untyped_token}"}
    )
    assert untyped_response.status_code == 401, untyped_response.text
"""

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", smoke, str(EXAMPLE)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
