from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"


def _load_workflow() -> dict[str, Any]:
    with WORKFLOW.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    assert isinstance(data, dict)
    return data


def test_publish_workflow_parses() -> None:
    workflow = _load_workflow()
    assert workflow["name"] == "publish"
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    expected_jobs = {
        "quality",
        "build",
        "validate",
        "publish-core",
        "verify-core",
        "publish-leaf",
        "verify-packages",
        "publish-fastapi",
        "verify-fastapi",
        "publish-meta",
        "smoke-test",
    }
    assert expected_jobs.issubset(jobs.keys())


def test_actionlint_validates_publish_workflow() -> None:
    actionlint = shutil.which("actionlint")
    if actionlint is None:
        raise AssertionError("actionlint is required for this test")
    result = subprocess.run(  # noqa: S603
        [actionlint, str(WORKFLOW)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_workflow_needs_references_are_valid() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]
    for job_name, job in jobs.items():
        needs = job.get("needs")
        if needs is None:
            continue
        if isinstance(needs, str):
            needs = [needs]
        for dependency in needs:
            assert dependency in jobs, f"{job_name} references unknown job {dependency}"


def test_workflow_job_graph_is_acyclic() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]

    def dependencies(job_name: str) -> list[str]:
        needs = jobs[job_name].get("needs")
        if needs is None:
            return []
        if isinstance(needs, str):
            return [needs]
        return list(needs)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(job_name: str) -> None:
        if job_name in visited:
            return
        if job_name in visiting:
            raise AssertionError(f"Cycle detected at {job_name}")
        visiting.add(job_name)
        for dependency in dependencies(job_name):
            visit(dependency)
        visiting.discard(job_name)
        visited.add(job_name)

    for job_name in jobs:
        visit(job_name)


def test_workflow_has_no_invalid_github_expressions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "github.ref_name#v" not in text
    assert "github.ref_name#V" not in text


def test_workflow_tag_trigger_is_a_glob() -> None:
    workflow = _load_workflow()
    workflow_any = cast(dict[Any, Any], workflow)
    triggers = workflow_any.get(True, workflow_any.get("on", {}))
    push_config = triggers["push"]
    tags = push_config["tags"]
    assert all("+" not in tag for tag in tags)


def test_workflow_dispatch_publish_defaults_to_false() -> None:
    workflow = _load_workflow()
    workflow_any = cast(dict[Any, Any], workflow)
    triggers = workflow_any.get(True, workflow_any.get("on", {}))
    publish_input = triggers["workflow_dispatch"]["inputs"]["publish"]
    assert publish_input["default"] is False


def test_topological_publish_order() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]

    def needs(job_name: str) -> set[str]:
        value = jobs[job_name].get("needs")
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        return set(value)

    assert "verify-core" in needs("publish-leaf")
    assert "verify-packages" in needs("publish-fastapi")
    assert "verify-fastapi" in needs("publish-meta")
    assert "verify-packages" in needs("publish-meta")
    assert "publish-meta" in needs("smoke-test")


def test_all_sixteen_distributions_are_represented() -> None:
    workflow = _load_workflow()
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    matrix_packages = jobs["publish-leaf"]["strategy"]["matrix"]["package"]
    expected_leaf = {
        "ai",
        "auth",
        "cache",
        "channels",
        "cli",
        "db",
        "email",
        "events",
        "i18n",
        "observability",
        "security",
        "storage",
        "tasks",
    }
    assert set(matrix_packages) == expected_leaf
    assert "for package in core fastapi storage db auth cache ai" in text
    assert "observability email channels i18n events security tasks cli; do" in text
    assert "uv build --package apyra" in text
