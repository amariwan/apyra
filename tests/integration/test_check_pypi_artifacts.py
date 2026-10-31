from __future__ import annotations

import hashlib
import http.client
import importlib.util
import io
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_pypi_artifacts.py"
spec = importlib.util.spec_from_file_location("check_pypi_artifacts", SCRIPT)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


def _write_artifact(directory: Path, name: str, content: bytes) -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def _run_main(argv: list[str]) -> int:
    original_argv = sys.argv
    sys.argv = argv
    try:
        return checker.main()
    finally:
        sys.argv = original_argv


def test_returns_zero_when_version_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_artifact(tmp_path, "example-1.0.0-py3-none-any.whl", b"wheel")
    monkeypatch.setattr(checker, "published_digests", lambda package, version: None)

    result = _run_main(
        [
            "check_pypi_artifacts.py",
            "--package",
            "example",
            "--version",
            "1.0.0",
            "--dist",
            str(tmp_path),
        ]
    )

    assert result == 0


def test_returns_zero_for_identical_published_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"wheel"
    path = _write_artifact(tmp_path, "example-1.0.0-py3-none-any.whl", content)
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(
        checker,
        "published_digests",
        lambda package, version: {path.name: digest},
    )

    result = _run_main(
        [
            "check_pypi_artifacts.py",
            "--package",
            "example",
            "--version",
            "1.0.0",
            "--dist",
            str(tmp_path),
        ]
    )

    assert result == 0


def test_fails_for_changed_published_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_artifact(tmp_path, "example-1.0.0-py3-none-any.whl", b"wheel")
    monkeypatch.setattr(
        checker,
        "published_digests",
        lambda package, version: {"example-1.0.0-py3-none-any.whl": "deadbeef"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_main(
            [
                "check_pypi_artifacts.py",
                "--package",
                "example",
                "--version",
                "1.0.0",
                "--dist",
                str(tmp_path),
            ]
        )

    assert exc_info.value.code != 0


def test_published_digests_returns_none_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_404(*args, **kwargs):
        raise HTTPError("url", 404, "not found", http.client.HTTPMessage(), None)

    monkeypatch.setattr("urllib.request.urlopen", raise_404)
    assert checker.published_digests("example", "1.0.0") is None


def test_published_digests_parses_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "urls": [
            {
                "filename": "example-1.0.0-py3-none-any.whl",
                "digests": {"sha256": "abc123"},
            }
        ]
    }

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode()),
    )
    assert checker.published_digests("example", "1.0.0") == {
        "example-1.0.0-py3-none-any.whl": "abc123"
    }
