from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "select_ci_tests.py"
spec = importlib.util.spec_from_file_location("select_ci_tests", SCRIPT)
assert spec is not None and spec.loader is not None
selector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = selector
spec.loader.exec_module(selector)
select_test_paths = cast(Callable[..., list[str]], selector.select_test_paths)


def test_empty_change_list_selects_no_tests() -> None:
    assert select_test_paths([]) == []


def test_leaf_source_change_selects_local_and_direct_dependent_tests() -> None:
    assert select_test_paths(["packages/auth/src/apyra/auth/service.py"]) == [
        "packages/auth/tests",
        "packages/fastapi/tests",
        "tests/integration",
    ]


def test_core_source_change_selects_full_suite() -> None:
    assert select_test_paths(["packages/core/src/apyra/core/settings.py"]) == ["."]


def test_package_test_change_selects_package_tests() -> None:
    assert select_test_paths(["packages/auth/tests/test_tokens.py"]) == ["packages/auth/tests"]


def test_package_manifest_change_selects_full_suite() -> None:
    assert select_test_paths(["packages/auth/pyproject.toml"]) == ["."]


def test_shared_and_unknown_changes_select_full_suite() -> None:
    assert select_test_paths(["tests/integration/test_auth_fastapi.py"]) == ["."]
    assert select_test_paths([".github/workflows/ci.yml"]) == ["."]
    assert select_test_paths(["README.md"]) == ["."]


def test_force_full_selects_full_suite_even_without_changed_files() -> None:
    assert select_test_paths([], force_full=True) == ["."]


def test_cli_writes_selected_paths_for_github_actions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(
        "CHANGED_FILES_JSON",
        json.dumps(["packages/auth/src/apyra/auth/service.py"]),
    )
    monkeypatch.setenv("CI_FORCE_FULL", "false")

    selector.main()

    assert capsys.readouterr().out == (
        'test-paths=["packages/auth/tests","packages/fastapi/tests","tests/integration"]\n'
    )
