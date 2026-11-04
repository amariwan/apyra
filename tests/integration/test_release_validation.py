from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from runpy import run_path
from typing import cast

import pytest

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


def test_release_validator_allows_only_a_bundled_manifest(tmp_path: Path) -> None:
    _write_artifact_placeholders(tmp_path)
    manifest = tmp_path / "apyra-0.1.0-manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    namespace = run_path(str(SCRIPT))
    validate_artifact_set = cast(
        Callable[[Path, Path | None], None], namespace["validate_artifact_set"]
    )

    validate_artifact_set(tmp_path, manifest)

    with pytest.raises(ValueError, match="Unexpected release artifacts"):
        validate_artifact_set(tmp_path, None)


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


def test_generated_quickstarts_validate_real_http_and_authentication(tmp_path: Path) -> None:
    namespace = run_path(str(SCRIPT))
    assert "validate_generated_quickstarts" in namespace
    validate_generated_quickstarts = cast(
        Callable[[Path, Path, Path], None], namespace["validate_generated_quickstarts"]
    )
    cli = shutil.which("apyra")
    assert cli is not None, "the workspace apyra CLI must be installed"

    validate_generated_quickstarts(Path(sys.executable), Path(cli), tmp_path)

    assert (tmp_path / "minimal-api" / "main.py").is_file()
    assert (tmp_path / "cookie-auth-api" / "main.py").is_file()


def test_generated_templates_validate_real_http() -> None:
    namespace = run_path(str(SCRIPT))
    assert "validate_generated_templates" in namespace
    validate_generated_templates = cast(
        Callable[[Path, Path, Path], None], namespace["validate_generated_templates"]
    )
    cli = shutil.which("apyra")
    assert cli is not None, "the workspace apyra CLI must be installed"

    import tempfile

    with tempfile.TemporaryDirectory(prefix="apyra-template-validate-") as temp_dir:
        validate_generated_templates(Path(sys.executable), Path(cli), Path(temp_dir))

    # files are removed with temp dir; just ensure function completed
