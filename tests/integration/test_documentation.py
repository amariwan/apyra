from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
MKDOCS_CONFIG = ROOT / "mkdocs.yml"
REFERENCE_DIR = ROOT / "docs" / "reference"


def _load_config() -> dict[str, Any]:
    assert MKDOCS_CONFIG.is_file(), "mkdocs.yml must define the documentation site"
    with MKDOCS_CONFIG.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    assert isinstance(config, dict)
    return config


def _navigation_paths(items: list[object]) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, str):
            paths.add(item)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.add(value)
                elif isinstance(value, list):
                    paths.update(_navigation_paths(value))
    return paths


def test_documentation_configuration_enables_required_site_features() -> None:
    config = _load_config()

    assert config["theme"]["name"] == "material"
    assert [palette["scheme"] for palette in config["theme"]["palette"]] == [
        "default",
        "slate",
    ]
    assert all(palette["toggle"]["name"] for palette in config["theme"]["palette"])

    plugins = config["plugins"]
    assert "search" in plugins
    assert any(isinstance(plugin, dict) and "mkdocstrings" in plugin for plugin in plugins)
    assert config["extra"]["version"]["provider"] == "mike"


def test_strict_documentation_build_creates_searchable_site(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the documentation"
    result = subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "--group",
            "docs",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(site_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (site_dir / "index.html").is_file()
    search_index = json.loads((site_dir / "search" / "search_index.json").read_text())
    assert search_index["docs"], "search index must contain rendered documentation"


def test_navigation_covers_the_p0_documentation_journey() -> None:
    config = _load_config()
    navigation_paths = _navigation_paths(config["nav"])
    required_paths = {
        "index.md",
        "getting-started/introduction.md",
        "getting-started/why-apyra.md",
        "getting-started/installation.md",
        "getting-started/quickstart.md",
        "guides/cli.md",
        "architecture/overview.md",
        "guides/authentication.md",
        "guides/database.md",
        "guides/messaging.md",
        "guides/tasks.md",
        "guides/workflow.md",
        "guides/observability.md",
        "guides/security.md",
        "guides/deployment.md",
        "guides/testing.md",
        "migrations/index.md",
        "project/changelog.md",
        "project/contributing.md",
        "guides/troubleshooting.md",
    }

    assert required_paths <= navigation_paths
    missing_files = sorted(
        path for path in navigation_paths if not (ROOT / "docs" / path).is_file()
    )
    assert not missing_files, f"navigation references missing pages: {missing_files}"


def test_every_public_package_has_a_generated_reference_page() -> None:
    package_names = {
        init_file.parent.name for init_file in (ROOT / "packages").glob("*/src/apyra/*/__init__.py")
    }
    assert package_names == {
        "ai",
        "application",
        "auth",
        "cache",
        "channels",
        "cli",
        "core",
        "db",
        "domain",
        "email",
        "events",
        "fastapi",
        "i18n",
        "messaging",
        "observability",
        "security",
        "storage",
        "tasks",
        "workflow",
    }

    for package_name in sorted(package_names):
        reference_page = REFERENCE_DIR / f"{package_name}.md"
        assert reference_page.is_file(), f"missing API reference for apyra.{package_name}"
        assert f"::: apyra.{package_name}" in reference_page.read_text(encoding="utf-8")

    assert (REFERENCE_DIR / "meta.md").is_file()

    navigation_paths = _navigation_paths(_load_config()["nav"])
    expected_reference_paths = {
        "reference/index.md",
        "reference/meta.md",
        *(f"reference/{package_name}.md" for package_name in package_names),
    }
    assert expected_reference_paths <= navigation_paths
