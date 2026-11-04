"""Verify distribution files against the manifest bundled with a release build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact_manifest(manifest_path: Path, dist: Path) -> None:
    """Require the manifest to describe exactly the wheel and sdist files in ``dist``."""
    manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    distributions = manifest.get("distributions") if isinstance(manifest, dict) else None
    if not isinstance(distributions, list) or not distributions:
        raise ValueError("manifest must contain a non-empty distributions list")

    expected: dict[str, str] = {}
    for distribution in distributions:
        if not isinstance(distribution, dict):
            raise ValueError("manifest distribution entries must be objects")
        for artifact_kind in ("wheel", "sdist"):
            artifact = distribution.get(artifact_kind)
            if not isinstance(artifact, dict):
                raise ValueError(f"{artifact_kind} metadata is missing")
            filename = artifact.get("filename")
            digest = artifact.get("sha256")
            if (
                not isinstance(filename, str)
                or Path(filename).name != filename
                or not isinstance(digest, str)
                or len(digest) != 64
            ):
                raise ValueError(f"invalid {artifact_kind} artifact metadata")
            if filename in expected:
                raise ValueError(f"duplicate artifact in manifest: {filename}")
            expected[filename] = digest

    actual = {
        path.name
        for path in dist.iterdir()
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    }
    missing = sorted(expected.keys() - actual)
    unexpected = sorted(actual - expected.keys())
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unlisted: " + ", ".join(unexpected))
        raise ValueError("artifact set does not match manifest (" + "; ".join(details) + ")")

    mismatches = [
        filename for filename, digest in expected.items() if _sha256(dist / filename) != digest
    ]
    if mismatches:
        raise ValueError("artifact SHA-256 mismatch: " + ", ".join(sorted(mismatches)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    verify_artifact_manifest(args.manifest, args.dist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
