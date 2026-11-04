from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fault_injection.py"
spec = importlib.util.spec_from_file_location("scripts.fault_injection", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
_log_check_failure = module._log_check_failure


def test_fault_injection_failures_use_module_logger_and_hide_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="scripts.fault_injection"):
        _log_check_failure("redis-check", RuntimeError("password=secret-value"))

    (record,) = caplog.records
    assert record.name == "scripts.fault_injection"
    assert record.getMessage() == "redis-check failed (RuntimeError)"
    assert "secret-value" not in record.getMessage()


def test_fault_injection_rejects_non_local_redis_before_docker_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(stdout="redis\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="local test service"):
        module._verify_disposable_target(
            "redis://redis.example.com:56379/15", "redis-test", "redis"
        )

    assert commands == []


def test_fault_injection_requires_test_label_and_matching_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(command)
        if command[1] == "inspect":
            return SimpleNamespace(stdout="redis\n")
        return SimpleNamespace(stdout="127.0.0.1:56379\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module._verify_disposable_target("redis://localhost:56379/15", "redis-test", "redis")

    with pytest.raises(ValueError, match="does not map"):
        module._verify_disposable_target("redis://localhost:6379/15", "redis-test", "redis")

    assert len(commands) == 4
