from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"


def _internal_dependents() -> dict[str, set[str]]:
    manifests = sorted(PACKAGES_DIR.glob("*/pyproject.toml"))
    package_dirs: dict[str, str] = {}
    projects: list[tuple[str, list[str]]] = []

    for manifest in manifests:
        with manifest.open("rb") as stream:
            project = tomllib.load(stream)["project"]
        project_name = project["name"]
        package_dir = manifest.parent.name
        package_dirs[project_name] = package_dir
        projects.append((package_dir, project.get("dependencies", [])))

    dependents = {package_dir: set() for package_dir, _ in projects}
    for package_dir, dependencies in projects:
        for dependency in dependencies:
            dependency_name = re.split(r"[<>=!~;\s]", dependency, maxsplit=1)[0]
            dependency_dir = package_dirs.get(dependency_name)
            if dependency_dir is not None:
                dependents[dependency_dir].add(package_dir)
    return dependents


def select_test_paths(changed_files: Sequence[str], force_full: bool = False) -> list[str]:
    if force_full:
        return ["."]
    if not changed_files:
        return []

    package_dirs = {manifest.parent.name for manifest in PACKAGES_DIR.glob("*/pyproject.toml")}
    source_packages: set[str] = set()
    test_packages: set[str] = set()

    for changed_file in changed_files:
        parts = PurePosixPath(changed_file).parts
        if len(parts) < 2 or parts[0] != "packages" or parts[1] not in package_dirs:
            return ["."]
        if len(parts) < 4:
            return ["."]

        package_dir, area = parts[1], parts[2]
        if area == "src":
            source_packages.add(package_dir)
        elif area == "tests":
            test_packages.add(package_dir)
        else:
            return ["."]

    if "core" in source_packages:
        return ["."]

    selected_packages = set(test_packages)
    if source_packages:
        dependents = _internal_dependents()
        pending = list(source_packages)
        selected_packages.update(source_packages)
        while pending:
            package_dir = pending.pop()
            for dependent in dependents[package_dir]:
                if dependent not in selected_packages:
                    selected_packages.add(dependent)
                    pending.append(dependent)

    paths = {
        f"packages/{package_dir}/tests"
        for package_dir in selected_packages
        if (PACKAGES_DIR / package_dir / "tests").is_dir()
    }
    if selected_packages and not paths:
        return ["."]
    if source_packages:
        paths.add("tests/integration")
    return sorted(paths)


def main() -> None:
    changed_files = json.loads(os.environ.get("CHANGED_FILES_JSON", "[]"))
    if not isinstance(changed_files, list) or not all(
        isinstance(path, str) for path in changed_files
    ):
        raise ValueError("CHANGED_FILES_JSON must be a JSON array of paths")

    force_full = os.environ.get("CI_FORCE_FULL", "").lower() == "true"
    test_paths = select_test_paths(changed_files, force_full)
    print(f"test-paths={json.dumps(test_paths, separators=(',', ':'))}")


if __name__ == "__main__":
    main()
