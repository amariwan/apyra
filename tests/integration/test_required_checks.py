"""Data-driven regression tests for scripts/check_required_ci.py."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_required_ci.py"
spec = importlib.util.spec_from_file_location("check_required_ci", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
determine_expected_jobs = module.determine_expected_jobs


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    full = dict(os.environ)
    full.update(env)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=full,
    )


def test_invalid_change_detection_output_on_pr_fails() -> None:
    result = _run(
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "CHANGES_CODE": "",
            "CHANGES_WORKFLOWS": "true",
            "RESULT_CHANGES": "success",
        }
    )
    assert result.returncode != 0
    assert "INVALID INPUT" in result.stderr


def test_missing_event_name_fails() -> None:
    result = _run(
        {
            "GITHUB_EVENT_NAME": "",
            "CHANGES_CODE": "true",
            "CHANGES_WORKFLOWS": "true",
            "RESULT_CHANGES": "success",
        }
    )
    assert result.returncode != 0


def test_change_detection_failure_forces_full_and_fails_if_jobs_missing() -> None:
    result = _run(
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "CHANGES_CODE": "true",
            "CHANGES_WORKFLOWS": "false",
            "RESULT_CHANGES": "failure",
            "RESULT_LOCK_CHECK": "success",
            "RESULT_QUALITY": "success",
            "RESULT_ACTIONLINT": "skipped",
            "RESULT_BUILD": "success",
            "RESULT_INSTALL_SMOKE": "success",
            "RESULT_ATTEST_BUILD": "skipped",
        }
    )
    # changes itself failed -> must fail
    assert result.returncode != 0


@pytest.mark.parametrize(
    "code,workflows,is_draft,event",
    [
        ("true", "false", False, "pull_request"),
        ("false", "true", False, "pull_request"),
        ("true", "true", False, "pull_request"),
        ("false", "false", False, "pull_request"),
    ],
)
def test_expected_jobs_for_pr_combinations(
    code: str, workflows: str, is_draft: bool, event: str
) -> None:
    expected = determine_expected_jobs(event, code, workflows, is_draft, False)
    # changes always expected
    assert "changes" in expected
    code_changed = code == "true"
    workflows_changed = workflows == "true"
    if code_changed or workflows_changed:
        assert "lock-check" in expected
        assert "quality" in expected
    else:
        assert "lock-check" not in expected
        assert "quality" not in expected
    if workflows_changed:
        assert "actionlint" in expected
    else:
        assert "actionlint" not in expected
    if (code_changed or workflows_changed) and not is_draft:
        assert "build" in expected
        assert "install-smoke" in expected
    else:
        assert "build" not in expected
        assert "install-smoke" not in expected
    # attest-build never on PR
    assert "attest-build" not in expected


@pytest.mark.parametrize(
    "event",
    ["push", "workflow_dispatch"],
)
def test_non_pr_forces_full_suite(event: str) -> None:
    expected = determine_expected_jobs(event, "", "", False, False)
    assert expected == {
        "changes",
        "lock-check",
        "quality",
        "actionlint",
        "build",
        "install-smoke",
        "attest-build",
    }


def test_draft_pr_skips_build() -> None:
    expected = determine_expected_jobs("pull_request", "true", "true", True, False)
    assert "build" not in expected
    assert "install-smoke" not in expected
    assert "lock-check" in expected
    assert "quality" in expected
    assert "actionlint" in expected


@pytest.mark.parametrize(
    "result,should_pass",
    [
        ("success", True),
        ("skipped", False),  # unexpected skip of mandatory job
        ("failure", False),
        ("cancelled", False),
        ("timed_out", False),
        ("", False),
    ],
)
def test_mandatory_job_result_enforcement(result: str, should_pass: bool) -> None:
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "CHANGES_CODE": "true",
        "CHANGES_WORKFLOWS": "false",
        "RESULT_CHANGES": "success",
        "RESULT_LOCK_CHECK": result,
        "RESULT_QUALITY": "success",
        "RESULT_ACTIONLINT": "skipped",
        "RESULT_BUILD": "success",
        "RESULT_INSTALL_SMOKE": "success",
        "RESULT_ATTEST_BUILD": "skipped",
    }
    r = _run(env)
    assert (r.returncode == 0) == should_pass, r.stderr


def test_optional_actionlint_skip_allowed() -> None:
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "CHANGES_CODE": "true",
        "CHANGES_WORKFLOWS": "false",
        "RESULT_CHANGES": "success",
        "RESULT_LOCK_CHECK": "success",
        "RESULT_QUALITY": "success",
        "RESULT_ACTIONLINT": "skipped",
        "RESULT_BUILD": "success",
        "RESULT_INSTALL_SMOKE": "success",
        "RESULT_ATTEST_BUILD": "skipped",
    }
    r = _run(env)
    assert r.returncode == 0, r.stderr


def test_unexpected_hard_failure_in_non_expected_job_fails() -> None:
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "CHANGES_CODE": "false",
        "CHANGES_WORKFLOWS": "false",
        "RESULT_CHANGES": "success",
        "RESULT_LOCK_CHECK": "skipped",
        "RESULT_QUALITY": "skipped",
        "RESULT_ACTIONLINT": "skipped",
        "RESULT_BUILD": "failure",
        "RESULT_INSTALL_SMOKE": "skipped",
        "RESULT_ATTEST_BUILD": "skipped",
    }
    r = _run(env)
    assert r.returncode != 0


def test_all_jobs_success_full_change_passes() -> None:
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "CHANGES_CODE": "true",
        "CHANGES_WORKFLOWS": "true",
        "RESULT_CHANGES": "success",
        "RESULT_LOCK_CHECK": "success",
        "RESULT_QUALITY": "success",
        "RESULT_ACTIONLINT": "success",
        "RESULT_BUILD": "success",
        "RESULT_INSTALL_SMOKE": "success",
        "RESULT_ATTEST_BUILD": "skipped",
    }
    r = _run(env)
    assert r.returncode == 0, r.stderr


def test_no_changes_pr_passes_when_all_skipped() -> None:
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "CHANGES_CODE": "false",
        "CHANGES_WORKFLOWS": "false",
        "RESULT_CHANGES": "success",
        "RESULT_LOCK_CHECK": "skipped",
        "RESULT_QUALITY": "skipped",
        "RESULT_ACTIONLINT": "skipped",
        "RESULT_BUILD": "skipped",
        "RESULT_INSTALL_SMOKE": "skipped",
        "RESULT_ATTEST_BUILD": "skipped",
    }
    r = _run(env)
    assert r.returncode == 0, r.stderr
