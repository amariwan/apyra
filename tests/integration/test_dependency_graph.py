from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"


def _load_projects() -> dict[str, set[str]]:
    projects: dict[str, set[str]] = {}
    for manifest in sorted(PACKAGES_DIR.glob("*/pyproject.toml")):
        with manifest.open("rb") as stream:
            data = tomllib.load(stream)
        name = data["project"]["name"]
        dependencies = data["project"].get("dependencies", [])
        internal = {
            dependency.split(">=")[0].split("<")[0].strip()
            for dependency in dependencies
            if dependency.startswith("apyra")
        }
        projects[name] = internal
    return projects


def _topological_order(projects: dict[str, set[str]]) -> list[str]:
    remaining = {name: set(deps) for name, deps in projects.items()}
    ordered: list[str] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            raise AssertionError("Dependency graph contains a cycle")
        for name in ready:
            ordered.append(name)
            del remaining[name]
            for deps in remaining.values():
                deps.discard(name)
    return ordered


def test_all_sixteen_distributions_are_present() -> None:
    projects = _load_projects()
    assert len(projects) == 16
    expected = {
        "apyra",
        "apyra-ai",
        "apyra-auth",
        "apyra-cache",
        "apyra-channels",
        "apyra-cli",
        "apyra-core",
        "apyra-db",
        "apyra-email",
        "apyra-events",
        "apyra-fastapi",
        "apyra-i18n",
        "apyra-observability",
        "apyra-security",
        "apyra-storage",
        "apyra-tasks",
    }
    assert set(projects) == expected


def test_dependency_graph_is_acyclic() -> None:
    projects = _load_projects()
    _topological_order(projects)


def test_dependency_graph_has_expected_release_order() -> None:
    projects = _load_projects()
    ordered = _topological_order(projects)
    assert ordered[0] == "apyra-core"
    assert ordered.index("apyra-fastapi") > ordered.index("apyra-auth")
    assert ordered.index("apyra-fastapi") > ordered.index("apyra-security")
    assert ordered.index("apyra-fastapi") > ordered.index("apyra-observability")
    assert projects["apyra"] == {"apyra-core"}


def test_fastapi_internal_dependencies_are_complete() -> None:
    projects = _load_projects()
    assert projects["apyra-fastapi"] == {
        "apyra-core",
        "apyra-auth",
        "apyra-security",
        "apyra-observability",
    }
