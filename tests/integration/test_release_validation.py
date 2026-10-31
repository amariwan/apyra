from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from runpy import run_path
from typing import cast

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_release.py"
PACKAGES = cast(list[str], run_path(str(SCRIPT))["PACKAGES"])


def _write_artifact_placeholders(dist: Path) -> None:
    for package in PACKAGES:
        normalized_name = package.replace("-", "_")
        (dist / f"{normalized_name}-0.1.0-py3-none-any.whl").touch()
        (dist / f"{normalized_name}-0.1.0.tar.gz").touch()


def _run_validator(dist: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--dist", str(dist)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_validator_rejects_unexpected_artifacts(tmp_path: Path) -> None:
    _write_artifact_placeholders(tmp_path)

    (tmp_path / "unexpected-0.1.0-py3-none-any.whl").touch()

    result = _run_validator(tmp_path)

    assert result.returncode != 0
    assert "Unexpected release artifacts" in result.stderr


def test_release_validator_rejects_missing_artifacts(tmp_path: Path) -> None:
    _write_artifact_placeholders(tmp_path)
    (tmp_path / "apyra_core-0.1.0-py3-none-any.whl").unlink()

    result = _run_validator(tmp_path)

    assert result.returncode != 0
    assert "Expected exactly one .whl artifact for apyra-core" in result.stderr
    assert "found 0" in result.stderr


def test_release_validator_rejects_duplicate_versions(tmp_path: Path) -> None:
    _write_artifact_placeholders(tmp_path)
    (tmp_path / "apyra_core-0.2.0-py3-none-any.whl").touch()

    result = _run_validator(tmp_path)

    assert result.returncode != 0
    assert "Expected exactly one .whl artifact for apyra-core" in result.stderr
    assert "found 2" in result.stderr
