"""Generate a machine-readable publication manifest for the Apyra release.

Reads each package manifest for name/version/dependencies, computes SHA-256 digests
of the built artifacts, and emits a JSON manifest describing the publication order
matching the ``publish.yml`` dependency chain.

Run after building::

    uv build --all-packages
    uv run python scripts/generate_manifest.py --dist dist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)

# Publication phases, matching .github/workflows/publish.yml.
_PUBLICATION_PHASES = [
    ("core", ["apyra-core"]),
    (
        "leaf",
        [
            "apyra-ai",
            "apyra-application",
            "apyra-auth",
            "apyra-cache",
            "apyra-channels",
            "apyra-cli",
            "apyra-db",
            "apyra-domain",
            "apyra-email",
            "apyra-events",
            "apyra-i18n",
            "apyra-messaging",
            "apyra-observability",
            "apyra-security",
            "apyra-storage",
            "apyra-tasks",
            "apyra-workflow",
        ],
    ),
    ("fastapi", ["apyra-fastapi"]),
    ("metapackage", ["apyra"]),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(name: str) -> str:
    return name.replace("-", "_")


def _read_metadata() -> dict[str, dict[str, object]]:
    metadata: dict[str, dict[str, object]] = {}
    for manifest in sorted((ROOT / "packages").glob("*/pyproject.toml")):
        project = tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]
        name = project["name"]
        metadata[name] = {
            "name": name,
            "version": project["version"],
            "dependencies": list(project.get("dependencies", [])),
            "optional_extras": {
                extra: list(deps)
                for extra, deps in project.get("optional-dependencies", {}).items()
            },
        }
    return metadata


def _build_manifest(dist: Path) -> dict[str, object]:
    metadata = _read_metadata()
    order: list[str] = []
    for _phase, names in _PUBLICATION_PHASES:
        order.extend(names)

    packages: list[dict[str, object]] = []
    for name in order:
        info = metadata[name]
        normalized = _normalize(name)
        wheel = dist / f"{normalized}-{info['version']}-py3-none-any.whl"
        sdist = dist / f"{normalized}-{info['version']}.tar.gz"
        if not wheel.is_file() or not sdist.is_file():
            raise FileNotFoundError(f"missing artifacts for {name}: {wheel.name}, {sdist.name}")
        packages.append(
            {
                "name": name,
                "version": info["version"],
                "pypi_destination": f"https://pypi.org/project/{name}/",
                "wheel": {
                    "filename": wheel.name,
                    "sha256": _sha256(wheel),
                },
                "sdist": {
                    "filename": sdist.name,
                    "sha256": _sha256(sdist),
                },
                "dependencies": info["dependencies"],
                "optional_extras": info["optional_extras"],
            }
        )

    versions = {str(info["version"]) for info in metadata.values()}
    if len(versions) != 1:
        raise ValueError("all distributions must use the same release version")

    return {
        "release": versions.pop(),
        "distributions": packages,
        "publication_order": order,
        "trusted_publishing": {
            "owner": "amariwan",
            "repository": "apyra",
            "workflow": "publish.yml",
            "environment_pattern": (
                "pypi-{suffix}, suffix = 'core' | 'fastapi' | 'meta' | leaf-name"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = _build_manifest(args.dist)
    output = args.output or args.dist / f"apyra-{manifest['release']}-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logger.info("wrote %s (%d distributions)", output, len(_read_metadata()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
