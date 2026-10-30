"""Validate all Apyra distributions in isolated environments."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYTHON = "/opt/homebrew/bin/python3.12"

PACKAGES = [
    "apyra-core",
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
    "apyra-security",
    "apyra-tasks",
    "apyra-cli",
    "apyra",
]
MODULES = {
    "apyra-core": "apyra.core",
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
    "apyra-security": "apyra.security",
    "apyra-tasks": "apyra.tasks",
    "apyra-cli": "apyra.cli",
    "apyra": "apyra.core",
}


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603


def main() -> int:
    for package in PACKAGES:
        venv = Path(f"/tmp/apyra-release-validate-{package}")  # noqa: S108
        subprocess.run([PYTHON, "-m", "venv", str(venv)], check=True)  # noqa: S603
        pip = venv / "bin" / "pip"
        wheel = DIST / f"{package.replace('-', '_')}-0.1.0-py3-none-any.whl"
        run([str(pip), "install", "--no-cache-dir", "--find-links", str(DIST), str(wheel)])
        command = [str(venv / "bin" / "python"), "-c", f"import {MODULES[package]}"]
        run(command)

    meta_venv = Path("/tmp/apyra-release-validate-meta")  # noqa: S108
    subprocess.run([PYTHON, "-m", "venv", str(meta_venv)], check=True)  # noqa: S603
    pip_command = [
        str(meta_venv / "bin" / "pip"),
        "install",
        "--no-cache-dir",
        "--find-links",
        str(DIST),
        "apyra[all]",
    ]
    run(pip_command)  # noqa: S603
    meta_import = "import apyra.core"
    run([str(meta_venv / "bin" / "python"), "-c", meta_import])
    print("RELEASE VALIDATION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
