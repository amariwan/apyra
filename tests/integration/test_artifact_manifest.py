from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from runpy import run_path
from typing import cast

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_artifact_manifest.py"
verify_artifact_manifest = cast(
    Callable[[Path, Path], None], run_path(str(SCRIPT))["verify_artifact_manifest"]
)


def _write_release_artifacts(dist: Path) -> dict[str, str]:
    contents = {
        "apyra_core-0.1.0-py3-none-any.whl": b"wheel bytes",
        "apyra_core-0.1.0.tar.gz": b"sdist bytes",
    }
    for filename, data in contents.items():
        (dist / filename).write_bytes(data)
    return {filename: hashlib.sha256(data).hexdigest() for filename, data in contents.items()}


def _write_manifest(path: Path, digests: dict[str, str]) -> None:
    manifest = {
        "release": "0.1.0",
        "distributions": [
            {
                "name": "apyra-core",
                "wheel": {
                    "filename": "apyra_core-0.1.0-py3-none-any.whl",
                    "sha256": digests["apyra_core-0.1.0-py3-none-any.whl"],
                },
                "sdist": {
                    "filename": "apyra_core-0.1.0.tar.gz",
                    "sha256": digests["apyra_core-0.1.0.tar.gz"],
                },
            }
        ],
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_artifact_manifest_accepts_the_exact_artifact_set(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    manifest_path = tmp_path / "manifest.json"
    digests = _write_release_artifacts(dist)
    _write_manifest(manifest_path, digests)

    verify_artifact_manifest(manifest_path, dist)


@pytest.mark.parametrize("failure", ["changed", "missing", "unlisted"])
def test_artifact_manifest_rejects_artifact_drift(tmp_path: Path, failure: str) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    manifest_path = tmp_path / "manifest.json"
    digests = _write_release_artifacts(dist)
    _write_manifest(manifest_path, digests)

    if failure == "changed":
        (dist / "apyra_core-0.1.0-py3-none-any.whl").write_bytes(b"changed wheel")
    elif failure == "missing":
        (dist / "apyra_core-0.1.0.tar.gz").unlink()
    else:
        (dist / "unexpected-0.1.0-py3-none-any.whl").write_bytes(b"extra wheel")

    with pytest.raises(ValueError, match="artifact"):
        verify_artifact_manifest(manifest_path, dist)
