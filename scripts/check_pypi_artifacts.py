"""Check whether a release version already exists on PyPI and compare artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def published_digests(package: str, version: str) -> dict[str, str] | None:
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    digests: dict[str, str] = {}
    for item in payload.get("urls", []):
        filename = item.get("filename")
        sha256 = item.get("digests", {}).get("sha256")
        if filename and sha256:
            digests[filename] = sha256
    return digests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()

    local_files = sorted(path for path in args.dist.iterdir() if path.is_file())
    if not local_files:
        raise SystemExit(f"No artifacts found in {args.dist}")

    existing = published_digests(args.package, args.version)
    if existing is None:
        print(f"{args.package} {args.version} is not published yet")
        return 0

    mismatches = []
    for path in local_files:
        expected = existing.get(path.name)
        actual = sha256_file(path)
        if expected is None:
            mismatches.append(f"{path.name}: not present in published release")
        elif expected != actual:
            mismatches.append(f"{path.name}: published {expected}, local {actual}")

    if mismatches:
        raise SystemExit(
            f"{args.package} {args.version} already exists on PyPI with different artifacts:\n"
            + "\n".join(mismatches)
        )

    print(f"{args.package} {args.version} already exists on PyPI with identical artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
