"""Verify the standalone enterprise-reference example's test suite.

The enterprise-reference example ships its own ``pyproject.toml`` (including a
pytest ``pythonpath`` configuration) and is intended to be exercised as a
self-contained project. Its test module imports ``main`` and registers
SQLAlchemy models on the shared ``apyra.db.Base``, so it is deliberately
excluded from the root ``pytest`` collection (``norecursedirs``) and run here in
a separate process to keep its top-level module names and declarative models
from colliding with the framework's test session.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_TESTS = ROOT / "examples" / "enterprise-reference" / "tests"


def test_enterprise_reference_example_suite_passes() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", str(EXAMPLE_TESTS), "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
