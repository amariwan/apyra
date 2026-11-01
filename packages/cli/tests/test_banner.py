"""Tests for the Apyra CLI startup banner."""

from __future__ import annotations

import importlib
import io

import pytest

from apyra.cli.banner import (
    BANNER_ART,
    BANNER_ENV_VAR,
    is_ci,
    print_banner,
    should_show_banner,
)

# ``apyra.cli.__init__`` re-exports the ``main`` function under the name ``main``,
# so the submodule must be resolved explicitly rather than via attribute access.
main_module = importlib.import_module("apyra.cli.main")


@pytest.mark.parametrize("variable", ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE"])
def test_is_ci_detects_common_variables(variable: str) -> None:
    assert is_ci({variable: "true"})


def test_is_ci_false_when_unset() -> None:
    assert not is_ci({})
    assert not is_ci({"CI": ""})
    assert not is_ci({"CI": "false"})


def test_should_show_banner_when_interactive() -> None:
    assert should_show_banner(is_terminal=True, environ={})


def test_should_show_banner_disabled_by_no_banner_flag() -> None:
    assert not should_show_banner(no_banner=True, is_terminal=True, environ={})


def test_should_show_banner_disabled_by_json_output() -> None:
    assert not should_show_banner(json_output=True, is_terminal=True, environ={})


def test_should_show_banner_disabled_when_not_terminal() -> None:
    assert not should_show_banner(is_terminal=False, environ={})


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE"])
def test_should_show_banner_disabled_by_env_var(value: str) -> None:
    assert not should_show_banner(is_terminal=True, environ={BANNER_ENV_VAR: value})


def test_should_show_banner_disabled_in_ci() -> None:
    assert not should_show_banner(is_terminal=True, environ={"CI": "1"})


def test_print_banner_includes_wordmark_version_and_environment() -> None:
    stream = io.StringIO()
    print_banner(version="1.2.3", environment="production", stream=stream)
    out = stream.getvalue()
    assert "Apyra" in out
    assert "1.2.3" in out
    assert "environment: production" in out


def test_print_banner_defaults_environment_to_development() -> None:
    stream = io.StringIO()
    print_banner(environ={}, stream=stream)
    assert "environment: development" in stream.getvalue()


def test_print_banner_reads_environment_from_env() -> None:
    stream = io.StringIO()
    print_banner(environ={"APYRA_ENVIRONMENT": "staging"}, stream=stream)
    assert "environment: staging" in stream.getvalue()


def test_print_banner_plain_fallback_has_no_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apyra.cli.banner._has_rich", lambda: False)
    stream = io.StringIO()
    print_banner(version="0.1.0", environment="staging", stream=stream)
    out = stream.getvalue()
    assert BANNER_ART in out
    assert "Apyra 0.1.0 · environment: staging" in out
    assert "\x1b[" not in out


def test_print_banner_rich_path_has_no_ansi_for_non_tty() -> None:
    pytest.importorskip("rich")
    stream = io.StringIO()
    print_banner(version="0.1.0", environment="production", stream=stream)
    out = stream.getvalue()
    assert BANNER_ART in out
    assert "Apyra 0.1.0" in out
    assert "environment: production" in out
    assert "\x1b[" not in out


def test_main_prints_banner_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(main_module, "should_show_banner", lambda **kwargs: True)
    monkeypatch.setattr(main_module, "print_banner", lambda **kwargs: calls.append(1))
    assert main_module.main(["check"]) == 0
    assert calls == [1]


def test_main_passes_no_banner_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def record(**kwargs: object) -> bool:
        received.update(kwargs)
        return False

    monkeypatch.setattr(main_module, "should_show_banner", record)
    assert main_module.main(["--no-banner", "check"]) == 0
    assert received["no_banner"] is True


def test_main_passes_json_output_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def record(**kwargs: object) -> bool:
        received.update(kwargs)
        return False

    monkeypatch.setattr(main_module, "should_show_banner", record)
    assert main_module.main(["doctor", "--json"]) == 0
    assert received["json_output"] is True


def test_main_does_not_print_banner_for_non_tty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main_module.main(["check"]) == 0
    captured = capsys.readouterr()
    assert BANNER_ART.splitlines()[0] not in captured.out
    assert "environment:" not in captured.out
