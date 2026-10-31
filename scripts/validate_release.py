"""Validate all Apyra wheels and source distributions in isolated environments."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYTHON = sys.executable
VENV_SCRIPTS = "Scripts" if sys.platform == "win32" else "bin"
PYTHON_EXECUTABLE = "python.exe" if sys.platform == "win32" else "python"
PIP_EXECUTABLE = "pip.exe" if sys.platform == "win32" else "pip"

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
    subprocess.run(command, check=True)  # noqa: S603


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


def validate_artifact_set(dist: Path) -> None:
    expected = {
        artifact_for_package(dist, package, suffix)
        for package in PACKAGES
        for suffix in (".whl", ".tar.gz")
    }
    unexpected = sorted(
        path.name for path in dist.iterdir() if path not in expected and path.name != ".gitignore"
    )
    if unexpected:
        raise ValueError("Unexpected release artifacts: " + ", ".join(unexpected))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Apyra wheels and source distributions in isolated environments"
    )
    parser.add_argument("--dist", type=Path, default=DIST, help="Directory containing built wheels")
    dist = parser.parse_args().dist.resolve()
    if not dist.is_dir():
        parser.error(f"wheel directory does not exist: {dist}")
    validate_artifact_set(dist)

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
        run(
            [
                str(meta_scripts / PIP_EXECUTABLE),
                "install",
                "--quiet",
                "--disable-pip-version-check",
                "--find-links",
                str(dist),
                "apyra[all]",
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

    print("RELEASE VALIDATION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
