from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
QUALITY_WORKFLOW = ROOT / ".github" / "workflows" / "_quality.yml"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    assert isinstance(data, dict)
    return data


def _workflow_call(workflow: dict[str, Any]) -> dict[str, Any]:
    workflow_any = cast(dict[Any, Any], workflow)
    return workflow_any.get(True, workflow_any.get("on", {}))["workflow_call"]


def test_ci_passes_changed_test_paths_to_quality() -> None:
    workflow = _load_yaml(CI_WORKFLOW)
    jobs = workflow["jobs"]
    changes = jobs["changes"]
    quality = jobs["quality"]

    assert "test-paths" in changes["outputs"]
    assert quality["with"]["test-paths"] == "${{ needs.changes.outputs.test-paths }}"
    assert "github.event_name != 'pull_request'" in quality["if"]

    filter_step = next(step for step in changes["steps"] if step.get("id") == "filter")
    selector_step = next(step for step in changes["steps"] if step.get("id") == "select-tests")
    assert filter_step["if"] == (
        "github.event_name == 'pull_request' || github.event_name == 'push'"
    )
    assert filter_step["with"]["list-files"] == "json"
    assert selector_step["env"]["CHANGED_FILES_JSON"] == (
        "${{ steps.filter.outputs.code_files || '[]' }}"
    )


def test_quality_default_runs_full_suite_for_publish_callers() -> None:
    workflow = _load_yaml(QUALITY_WORKFLOW)
    inputs = _workflow_call(workflow)["inputs"]
    assert inputs["test-paths"]["type"] == "string"
    assert inputs["test-paths"]["default"] == '["."]'

    publish_quality = _load_yaml(PUBLISH_WORKFLOW)["jobs"]["quality"]
    assert publish_quality["with"] == {"python-version": "${{ matrix.python-version }}"}


def test_quality_runs_pytest_with_paths_from_environment() -> None:
    workflow = _load_yaml(QUALITY_WORKFLOW)
    test_job = workflow["jobs"]["test"]
    pytest_step = next(step for step in test_job["steps"] if step.get("name") == "pytest")

    assert pytest_step["env"]["TEST_PATHS"] == "${{ inputs.test-paths }}"
    assert 'json.loads(os.environ["TEST_PATHS"])' in pytest_step["run"]
    assert "subprocess.run" in pytest_step["run"]


def test_security_scans_run_once_and_bandit_errors_are_not_ignored() -> None:
    workflow = _load_yaml(QUALITY_WORKFLOW)
    security_job = workflow["jobs"]["security"]
    assert security_job["if"] == "inputs.python-version == '3.12'"

    bandit_step = next(step for step in security_job["steps"] if step.get("name") == "bandit")
    assert "|| true" not in bandit_step["run"]


def test_quality_matrix_keeps_both_supported_python_versions() -> None:
    workflow = _load_yaml(CI_WORKFLOW)
    assert workflow["jobs"]["quality"]["strategy"]["matrix"]["python-version"] == [
        "3.12",
        "3.13",
    ]
