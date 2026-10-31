"""Validate that all mandatory CI jobs succeeded for the current change set.

This script is the data-driven required-checks aggregator used by the
``required-checks`` job in ``.github/workflows/ci.yml``.  It derives the set of
mandatory jobs from the change-detection outputs and fails unless every one of
them reports ``success``.

Exit codes:
    0  all mandatory jobs succeeded
    1  one or more mandatory jobs did not succeed (or inputs were invalid)
"""

from __future__ import annotations

import os
import sys

VALID_BOOL = {"true", "false"}
FAILURE_STATUSES = {"failure", "cancelled", "timed_out", "action_required"}


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _is_truthy(value: str) -> bool:
    return value.lower() == "true"


def determine_expected_jobs(
    event_name: str,
    code: str,
    workflows: str,
    is_draft: bool,
    changes_failed: bool,
) -> set[str]:
    """Return the set of job names that must have succeeded."""
    is_pr = event_name == "pull_request"

    # Missing/invalid change-detection output on a PR is never silently allowed.
    if is_pr:
        if code not in VALID_BOOL or workflows not in VALID_BOOL:
            raise ValueError(
                f"invalid change-detection output: code={code!r}, workflows={workflows!r}"
            )

    # If change detection itself failed, be conservative and require everything.
    if changes_failed:
        code = "true"
        workflows = "true"

    # Non-PR events (push/dispatch) force a full run.
    if not is_pr:
        code_changed = True
        workflows_changed = True
    else:
        code_changed = _is_truthy(code)
        workflows_changed = _is_truthy(workflows)

    expected: set[str] = {"changes"}

    if code_changed or workflows_changed:
        expected.add("lock-check")
        expected.add("quality")

    if workflows_changed or not is_pr:
        expected.add("actionlint")

    build_expected = (code_changed or workflows_changed) and not is_draft
    if build_expected:
        expected.add("build")
        expected.add("install-smoke")

    if build_expected and not is_pr:
        expected.add("attest-build")

    return expected


def main() -> int:
    event_name = _env("GITHUB_EVENT_NAME") or _env("EVENT_NAME")
    code = _env("CHANGES_CODE")
    workflows = _env("CHANGES_WORKFLOWS")
    is_draft = _is_truthy(_env("IS_DRAFT"))
    changes_result = _env("RESULT_CHANGES") or "success"

    job_results = {
        "changes": changes_result,
        "lock-check": _env("RESULT_LOCK_CHECK"),
        "quality": _env("RESULT_QUALITY"),
        "actionlint": _env("RESULT_ACTIONLINT"),
        "build": _env("RESULT_BUILD"),
        "install-smoke": _env("RESULT_INSTALL_SMOKE"),
        "attest-build": _env("RESULT_ATTEST_BUILD"),
    }

    changes_failed = changes_result in FAILURE_STATUSES or changes_result == ""

    try:
        expected = determine_expected_jobs(event_name, code, workflows, is_draft, changes_failed)
    except ValueError as exc:
        print(f"INVALID INPUT: {exc}", file=sys.stderr)
        return 1

    # Missing change-detection output on a PR is already handled above; but also
    # guard against completely empty event context.
    if not event_name:
        print("INVALID INPUT: GITHUB_EVENT_NAME is required", file=sys.stderr)
        return 1

    print(f"event={event_name} code={code!r} workflows={workflows!r} draft={is_draft}")
    print(f"expected mandatory jobs: {sorted(expected)}")

    failed = False
    for job in sorted(expected):
        result = job_results.get(job, "")
        print(f"  {job}: {result or '<missing>'}")
        if result != "success":
            failed = True
            print(f"  -> FAIL: {job} expected success, got {result or '<missing>'}")

    # Any executed (non-skipped) job reporting a hard failure is an error even if
    # it was not in the expected set.
    for job, result in job_results.items():
        if result in FAILURE_STATUSES:
            print(f"  {job}: {result} (unexpected failure)", file=sys.stderr)
            failed = True

    # Unexpected skip of an expected job is already covered (result != success).
    # Additionally, a non-expected job that is unexpectedly skipped is fine, but
    # a non-expected job reporting 'skipped' while expected set is empty-ish is ok.

    if failed:
        print("REQUIRED CHECKS: FAIL", file=sys.stderr)
        return 1

    print("REQUIRED CHECKS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
