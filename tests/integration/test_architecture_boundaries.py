import ast
import re
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path
from typing import cast

_ALLOWED_CORE_EXTERNAL_IMPORT_ROOTS = {"pydantic", "pydantic_settings"}


def _imported_names(node: ast.Import | ast.ImportFrom, package_parts: list[str]) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    if node.level == 0:
        target_parts = node.module.split(".") if node.module else []
    else:
        base_parts = package_parts[: len(package_parts) - node.level + 1]
        module_parts = node.module.split(".") if node.module else []
        target_parts = [*base_parts, *module_parts]
    if not target_parts:
        return []

    if target_parts == ["apyra"]:
        return [f"apyra.{alias.name}" for alias in node.names]
    return [".".join(target_parts)]


def _is_forbidden_import(imported_name: str) -> bool:
    parts = imported_name.split(".")
    if parts[0] == "apyra":
        return len(parts) > 1 and parts[1] != "core"
    return (
        parts[0] not in sys.stdlib_module_names
        and parts[0] not in _ALLOWED_CORE_EXTERNAL_IMPORT_ROOTS
    )


def test_boundary_checker_detects_sibling_namespace_import_forms() -> None:
    examples = (
        ("from apyra import auth", ["apyra", "core"], "apyra.auth", True),
        ("from apyra.auth import JWTAuthenticator", ["apyra", "core"], "apyra.auth", True),
        ("from .. import fastapi", ["apyra", "core"], "apyra.fastapi", True),
        ("import fastapi", ["apyra", "core"], "fastapi", True),
        ("from sqlalchemy.orm import Session", ["apyra", "core"], "sqlalchemy.orm", True),
        ("import redis.asyncio", ["apyra", "core"], "redis.asyncio", True),
        ("from apyra.core import CoreSettings", ["apyra", "core"], "apyra.core", False),
        (
            "from pydantic_settings import BaseSettings",
            ["apyra", "core"],
            "pydantic_settings",
            False,
        ),
        ("from pathlib import Path", ["apyra", "core"], "pathlib", False),
    )

    for source, package_parts, expected_name, forbidden in examples:
        node = ast.parse(source).body[0]

        assert isinstance(node, (ast.Import, ast.ImportFrom))
        imported_names = _imported_names(node, package_parts)
        assert imported_names == [expected_name]
        assert _is_forbidden_import(imported_names[0]) is forbidden


def test_core_has_no_cross_package_static_imports() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    core_root = repository_root / "packages/core/src/apyra/core"
    violations: list[str] = []

    for source_path in sorted(core_root.rglob("*.py")):
        relative_path = source_path.relative_to(core_root)
        package_parts = ["apyra", "core", *relative_path.parent.parts]
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported_name in _imported_names(node, package_parts):
                if _is_forbidden_import(imported_name):
                    location = source_path.relative_to(repository_root)
                    violations.append(f"{location}:{node.lineno}: {imported_name}")

    assert not violations, (
        "Core imports must use stdlib, the explicit dependency allowlist, and its own package: "
        + "; ".join(violations)
    )


def test_workspace_package_dependencies_are_declared_and_acyclic() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    package_roots = {
        package_path.name: package_path
        for package_path in (repository_root / "packages").iterdir()
        if (package_path / "pyproject.toml").is_file()
    }
    distribution_names: dict[str, str] = {}
    package_projects: dict[str, dict[str, object]] = {}
    for package_name, package_path in package_roots.items():
        project_data = tomllib.loads((package_path / "pyproject.toml").read_text(encoding="utf-8"))
        project = cast(dict[str, object], project_data["project"])
        distribution = re.sub(r"[-_.]+", "-", cast(str, project["name"])).lower()
        distribution_names[distribution] = package_name
        package_projects[package_name] = project

    dependencies: dict[str, set[str]] = {package: set() for package in package_roots}
    for package_name, project in package_projects.items():
        requirements = list(cast(list[str], project.get("dependencies", [])))
        optional_dependencies = cast(dict[str, list[str]], project.get("optional-dependencies", {}))
        for optional_group in optional_dependencies.values():
            requirements.extend(optional_group)
        for requirement in requirements:
            match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
            if match is None:
                continue
            distribution = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            target = distribution_names.get(distribution)
            if target is not None:
                dependencies[package_name].add(target)

    undeclared_imports: list[str] = []
    for package_name, package_path in package_roots.items():
        source_root = package_path / "src"
        if not source_root.is_dir():
            continue
        for source_path in sorted(source_root.rglob("*.py")):
            relative_parts = list(source_path.relative_to(source_root).with_suffix("").parts)
            if relative_parts[-1] == "__init__":
                relative_parts.pop()
            module_parts = ["apyra", *relative_parts]
            package_parts = module_parts if source_path.name == "__init__.py" else module_parts[:-1]
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for imported_name in _imported_names(node, package_parts):
                    parts = imported_name.split(".")
                    if (
                        len(parts) > 1
                        and parts[0] == "apyra"
                        and parts[1] in package_roots
                        and parts[1] != package_name
                        and parts[1] not in dependencies[package_name]
                    ):
                        relative_path = source_path.relative_to(repository_root)
                        undeclared_imports.append(
                            f"{relative_path}:{node.lineno}: "
                            f"{parts[1]} is not a declared dependency"
                        )

    assert not undeclared_imports, (
        "Cross-package source imports must have a direct project dependency: "
        + "; ".join(undeclared_imports)
    )

    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[str] = []

    def visit(package_name: str) -> None:
        state[package_name] = 1
        stack.append(package_name)
        for dependency in sorted(dependencies[package_name]):
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state[dependency] == 1:
                cycle_start = stack.index(dependency)
                cycles.append(" -> ".join([*stack[cycle_start:], dependency]))
        stack.pop()
        state[package_name] = 2

    for package_name in sorted(package_roots):
        if state.get(package_name, 0) == 0:
            visit(package_name)

    assert not cycles, "Workspace distribution dependencies must be acyclic: " + "; ".join(cycles)


def test_external_runtime_imports_have_declared_package_dependencies() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    import_distributions = packages_distributions()
    undeclared_imports: list[str] = []

    for package_path in sorted((repository_root / "packages").iterdir()):
        manifest = package_path / "pyproject.toml"
        source_root = package_path / "src"
        if not manifest.is_file() or not source_root.is_dir() or package_path.name == "meta":
            continue

        project = cast(
            dict[str, object], tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]
        )
        requirements = list(cast(list[str], project.get("dependencies", [])))
        optional_dependencies = cast(dict[str, list[str]], project.get("optional-dependencies", {}))
        for group in optional_dependencies.values():
            requirements.extend(group)
        declared = {
            re.sub(r"[-_.]+", "-", match.group(1)).lower()
            for requirement in requirements
            if (match := re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement))
        }

        for source_path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported_roots = [node.module.split(".")[0]]
                else:
                    continue

                for root in imported_roots:
                    if root in sys.stdlib_module_names or root == "apyra":
                        continue
                    providers = import_distributions.get(root, [])
                    normalized_providers = {
                        re.sub(r"[-_.]+", "-", provider).lower() for provider in providers
                    }
                    if not normalized_providers or not declared.intersection(normalized_providers):
                        location = source_path.relative_to(repository_root)
                        undeclared_imports.append(f"{location}:{node.lineno}: {root}")

    assert not undeclared_imports, (
        "Third-party source imports must be declared by the distribution or one of its extras: "
        + "; ".join(undeclared_imports)
    )
