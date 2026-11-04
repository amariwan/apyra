"""Validate all Apyra wheels and source distributions in isolated environments."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYTHON = sys.executable
VENV_SCRIPTS = "Scripts" if sys.platform == "win32" else "bin"
PYTHON_EXECUTABLE = "python.exe" if sys.platform == "win32" else "python"
PIP_EXECUTABLE = "pip.exe" if sys.platform == "win32" else "pip"
APYRA_EXECUTABLE = "apyra.exe" if sys.platform == "win32" else "apyra"

_MINIMAL_QUICKSTART_CHECK = """
from fastapi.testclient import TestClient

from main import app

with TestClient(app) as client:
    health = client.get("/api/health")
    assert health.status_code == 200, health.text
    assert health.json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
"""

_COOKIE_AUTH_QUICKSTART_CHECK = """
import os
import time

import jwt
from fastapi.testclient import TestClient

from main import app

now = int(time.time())
access_token = jwt.encode(
    {
        "sub": "quickstart-user",
        "iat": now,
        "exp": now + 300,
        "iss": "apyra-quickstart",
        "aud": "apyra-quickstart-api",
        "type": "access",
        "jti": "quickstart-token",
        "roles": ["developer"],
        "scopes": ["write"],
    },
    os.environ["AUTH_HS_SECRET"],
    algorithm="HS256",
)

with TestClient(app) as client:
    assert client.get("/csrf").status_code == 401
    client.cookies.set("access_token", access_token)
    csrf_response = client.get("/csrf")
    assert csrf_response.status_code == 200, csrf_response.text
    csrf_token = csrf_response.json()["csrf_token"]
    assert client.post("/write").status_code == 403
    protected = client.post("/write", headers={"X-CSRF-Token": csrf_token})
    assert protected.status_code == 200, protected.text
    assert protected.json() == {"ok": True}
"""

PACKAGES = [
    "apyra-application",
    "apyra-core",
    "apyra-domain",
    "apyra-fastapi",
    "apyra-db",
    "apyra-auth",
    "apyra-storage",
    "apyra-cache",
    "apyra-ai",
    "apyra-observability",
    "apyra-email",
    "apyra-channels",
    "apyra-i18n",
    "apyra-events",
    "apyra-messaging",
    "apyra-security",
    "apyra-tasks",
    "apyra-workflow",
    "apyra-cli",
    "apyra",
]
MODULES = {
    "apyra-application": "apyra.application",
    "apyra-core": "apyra.core",
    "apyra-domain": "apyra.domain",
    "apyra-fastapi": "apyra.fastapi",
    "apyra-db": "apyra.db",
    "apyra-auth": "apyra.auth",
    "apyra-storage": "apyra.storage",
    "apyra-cache": "apyra.cache",
    "apyra-ai": "apyra.ai",
    "apyra-observability": "apyra.observability",
    "apyra-email": "apyra.email",
    "apyra-channels": "apyra.channels",
    "apyra-i18n": "apyra.i18n",
    "apyra-events": "apyra.events",
    "apyra-messaging": "apyra.messaging",
    "apyra-security": "apyra.security",
    "apyra-tasks": "apyra.tasks",
    "apyra-workflow": "apyra.workflow",
    "apyra-cli": "apyra.cli",
    "apyra": "apyra.core",
}


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)  # noqa: S603


def validate_generated_quickstarts(python: Path, cli: Path, root: Path) -> None:
    """Generate both starter projects and validate their HTTP and security behavior."""
    run([str(cli), "new", "minimal-api"], cwd=root)
    run([str(python), "-c", _MINIMAL_QUICKSTART_CHECK], cwd=root / "minimal-api")

    run([str(cli), "new", "cookie-auth-api", "--template", "cookie-auth"], cwd=root)
    environment = os.environ.copy()
    environment.update(
        {
            "APYRA_COOKIE_SECURE": "false",
            "APYRA_CSRF_SECRET": "quickstart-csrf-secret-with-at-least-32-bytes",
            "AUTH_ALGORITHMS": "HS256",
            "AUTH_AUDIENCE": "apyra-quickstart-api",
            "AUTH_EXPECTED_ACCESS_TOKEN_TYPE": "access",
            "AUTH_HS_SECRET": "quickstart-hs-secret-with-at-least-32-bytes",
            "AUTH_ISSUER": "apyra-quickstart",
            "AUTH_MODE": "hs",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    run(
        [str(python), "-c", _COOKIE_AUTH_QUICKSTART_CHECK],
        cwd=root / "cookie-auth-api",
        env=environment,
    )
    print("QUICKSTART VALIDATION OK")


_MODULAR_MONOLITH_CHECK = """
from fastapi.testclient import TestClient

from main import app

with TestClient(app) as client:
    response = client.get("/api/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
"""

_DISTRIBUTED_CHECK = """
import os

from fastapi.testclient import TestClient

from main import app

os.environ.setdefault("AUTH_MODE", "hs")
os.environ.setdefault("AUTH_HS_SECRET", "distributed-validation-secret-with-32-bytes")
os.environ.setdefault("AUTH_ALGORITHMS", "HS256")
os.environ.setdefault("AUTH_ISSUER", "apyra-reference")
os.environ.setdefault("AUTH_AUDIENCE", "apyra-reference-api")
os.environ.setdefault("AUTH_EXPECTED_ACCESS_TOKEN_TYPE", "access")
os.environ.setdefault("APYRA_REFERENCE_JWT_SECRET", "distributed-validation-secret-with-32-bytes")

with TestClient(app) as client:
    health = client.get("/api/health")
    assert health.status_code == 200, health.text
    assert health.json() == {"status": "ok"}
    token = client.post("/api/auth/token", params={"customer_id": "cust-1"})
    assert token.status_code == 200, token.text
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    created = client.post("/api/orders", params={"customer_id": "cust-1"}, headers=headers)
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "created"
"""


def validate_generated_templates(python: Path, cli: Path, root: Path) -> None:
    """Generate the golden-path templates and validate their basic HTTP behavior."""
    run([str(cli), "new", "modular-monolith-api", "--template", "modular-monolith"], cwd=root)
    run([str(python), "-c", _MODULAR_MONOLITH_CHECK], cwd=root / "modular-monolith-api")

    run([str(cli), "new", "distributed-api", "--template", "distributed"], cwd=root)
    environment = os.environ.copy()
    environment.update(
        {
            "AUTH_MODE": "hs",
            "AUTH_ALGORITHMS": "HS256",
            "AUTH_AUDIENCE": "apyra-reference-api",
            "AUTH_EXPECTED_ACCESS_TOKEN_TYPE": "access",
            "AUTH_HS_SECRET": "distributed-validation-secret-with-32-bytes",
            "AUTH_ISSUER": "apyra-reference",
            "APYRA_REFERENCE_JWT_SECRET": "distributed-validation-secret-with-32-bytes",
            "DB_BACKEND": "sqlite",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    run(
        [str(python), "-c", _DISTRIBUTED_CHECK],
        cwd=root / "distributed-api",
        env=environment,
    )
    print("TEMPLATE VALIDATION OK")


def artifact_for_package(dist: Path, package: str, suffix: str) -> Path:
    artifacts = [
        path for path in dist.glob(f"{package.replace('-', '_')}-*{suffix}") if path.is_file()
    ]
    if len(artifacts) != 1:
        raise FileNotFoundError(
            f"Expected exactly one {suffix} artifact for {package} in {dist}, "
            f"found {len(artifacts)}"
        )
    return artifacts[0]


def validate_artifact_set(dist: Path, manifest: Path | None = None) -> None:
    expected = {
        artifact_for_package(dist, package, suffix)
        for package in PACKAGES
        for suffix in (".whl", ".tar.gz")
    }
    allowed = expected | {dist / ".gitignore"}
    if manifest is not None:
        allowed.add(manifest)
    if manifest is not None and (manifest.parent != dist or not manifest.is_file()):
        raise FileNotFoundError(
            "release manifest must be an existing file inside the dist directory"
        )
    unexpected = sorted(path.name for path in dist.iterdir() if path not in allowed)
    if unexpected:
        raise ValueError("Unexpected release artifacts: " + ", ".join(unexpected))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Apyra wheels and source distributions in isolated environments"
    )
    parser.add_argument("--dist", type=Path, default=DIST, help="Directory containing built wheels")
    parser.add_argument(
        "--manifest", type=Path, help="Bundled release manifest verified against the artifacts"
    )
    args = parser.parse_args()
    dist = args.dist.resolve()
    if not dist.is_dir():
        parser.error(f"wheel directory does not exist: {dist}")
    manifest = args.manifest.resolve() if args.manifest is not None else None
    validate_artifact_set(dist, manifest)

    with tempfile.TemporaryDirectory(prefix="apyra-release-validate-") as temp_dir:
        root = Path(temp_dir)
        for package in PACKAGES:
            venv = root / package
            subprocess.run([PYTHON, "-m", "venv", str(venv)], check=True)  # noqa: S603
            scripts = venv / VENV_SCRIPTS
            pip = scripts / PIP_EXECUTABLE
            wheel = artifact_for_package(dist, package, ".whl")
            sdist = artifact_for_package(dist, package, ".tar.gz")
            run(
                [
                    str(pip),
                    "install",
                    "--quiet",
                    "--disable-pip-version-check",
                    "--find-links",
                    str(dist),
                    str(wheel),
                ]
            )
            module = MODULES[package]
            import_check = (
                "import importlib; from importlib.resources import files; "
                f"module = importlib.import_module('{module}'); "
                "assert files(module).joinpath('py.typed').is_file()"
            )
            run([str(scripts / PYTHON_EXECUTABLE), "-c", import_check])
            run(
                [
                    str(pip),
                    "install",
                    "--quiet",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--force-reinstall",
                    str(sdist),
                ]
            )
            run([str(scripts / PYTHON_EXECUTABLE), "-c", import_check])

        meta_venv = root / "apyra-all"
        subprocess.run([PYTHON, "-m", "venv", str(meta_venv)], check=True)  # noqa: S603
        meta_scripts = meta_venv / VENV_SCRIPTS
        local_wheels = [
            str(artifact_for_package(dist, package, ".whl"))
            for package in PACKAGES
            if package != "apyra"
        ]
        meta_wheel = artifact_for_package(dist, "apyra", ".whl")
        run(
            [
                str(meta_scripts / PIP_EXECUTABLE),
                "install",
                "--quiet",
                "--disable-pip-version-check",
                "--find-links",
                str(dist),
                *local_wheels,
                f"{meta_wheel}[all]",
            ]
        )
        module_names = tuple(dict.fromkeys(MODULES.values()))
        import_check = (
            "import importlib; from importlib.resources import files; "
            f"module_names = {module_names!r}; "
            "modules = [importlib.import_module(name) for name in module_names]; "
            "missing = [module.__name__ for module in modules "
            "if not files(module).joinpath('py.typed').is_file()]; "
            "assert not missing, f'missing py.typed markers: {missing}'"
        )
        run([str(meta_scripts / PYTHON_EXECUTABLE), "-c", import_check])

        run(
            [
                str(meta_scripts / PIP_EXECUTABLE),
                "install",
                "--quiet",
                "--disable-pip-version-check",
                "httpx2>=2,<3",
            ]
        )
        quickstart_root = root / "quickstarts"
        quickstart_root.mkdir()
        validate_generated_quickstarts(
            meta_scripts / PYTHON_EXECUTABLE,
            meta_scripts / APYRA_EXECUTABLE,
            quickstart_root,
        )

        template_root = root / "templates"
        template_root.mkdir()
        validate_generated_templates(
            meta_scripts / PYTHON_EXECUTABLE,
            meta_scripts / APYRA_EXECUTABLE,
            template_root,
        )

    print("RELEASE VALIDATION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
