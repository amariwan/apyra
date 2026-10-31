import os
import subprocess
import sys
from pathlib import Path

import pytest

from apyra.cli.main import main


def test_new_project_creates_files(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["new", "demo"]) == 0
        assert (tmp_path / "demo" / "main.py").is_file()
        assert (tmp_path / "demo" / "pyproject.toml").is_file()
        generated_main = (tmp_path / "demo" / "main.py").read_text()
        assert '@router.get("/health")' in generated_main
        assert "require_csrf" not in generated_main
    finally:
        os.chdir(original)


def test_new_cookie_auth_template_generates_csrf_protected_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["new", "cookie_demo", "--template", "cookie-auth"]) == 0

    generated = tmp_path / "cookie_demo"
    source = (generated / "main.py").read_text()
    readme = (generated / "README.md").read_text()
    pyproject = (generated / "pyproject.toml").read_text()

    assert '@router.get("/csrf")' in source
    assert '@router.post("/write")' in source
    assert "Depends(get_current_token)" in source
    assert "require_csrf" in source
    assert "APYRA_CSRF_SECRET" in source
    assert "APYRA_COOKIE_SECURE" in source
    assert "APYRA_CSRF_SECRET" in readme
    assert "Origin" in readme
    assert "apyra-fastapi" in pyproject
    with pytest.raises(FileExistsError, match="project directory already exists"):
        main(["new", "cookie_demo", "--template", "cookie-auth"])
    assert (generated / "main.py").read_text() == source


def test_cookie_auth_template_protects_routes_and_sets_secure_csrf_cookie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APYRA_CSRF_SECRET", "x" * 32)
    assert main(["new", "cookie_demo", "--template", "cookie-auth"]) == 0

    source_file = tmp_path / "cookie_demo" / "main.py"
    sys.path.insert(0, str(source_file.parent))
    try:
        import importlib

        generated_app = importlib.import_module("main")
        generated_app.app.dependency_overrides[generated_app.get_current_token] = lambda: {
            "sub": "user-1"
        }
        from apyra.security import generate_csrf_token
        from fastapi.testclient import TestClient

        with TestClient(generated_app.app) as client:
            assert client.get("/csrf").status_code == 401

            access_token = "provider-issued-token"
            client.cookies.set("access_token", access_token)
            csrf_response = client.get("/csrf")
            assert csrf_response.status_code == 200
            csrf_token = csrf_response.json()["csrf_token"]
            set_cookie = csrf_response.headers["set-cookie"].lower()
            assert "csrf_token=" in set_cookie
            assert "secure" in set_cookie
            assert "httponly" not in set_cookie
            assert "samesite=lax" in set_cookie

            assert client.post("/write").status_code == 403
            assert client.post("/write", headers={"X-CSRF-Token": "wrong"}).status_code == 403

            wrong_binding_token = generate_csrf_token("x" * 32, binding="other")
            assert (
                client.post(
                    "/write",
                    headers={
                        "X-CSRF-Token": wrong_binding_token,
                        "Cookie": f"access_token={access_token}; csrf_token={wrong_binding_token}",
                    },
                ).status_code
                == 403
            )

            assert (
                client.post(
                    "/write",
                    headers={
                        "X-CSRF-Token": csrf_token,
                        "Cookie": f"access_token={access_token}; csrf_token={csrf_token}",
                    },
                ).status_code
                == 200
            )
    finally:
        sys.path.remove(str(source_file.parent))
        sys.modules.pop("main", None)


def test_cookie_auth_template_can_disable_secure_for_local_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APYRA_CSRF_SECRET", "x" * 32)
    monkeypatch.setenv("APYRA_COOKIE_SECURE", "false")
    assert main(["new", "cookie_demo", "--template", "cookie-auth"]) == 0

    source_file = tmp_path / "cookie_demo" / "main.py"
    sys.path.insert(0, str(source_file.parent))
    try:
        import importlib

        generated_app = importlib.import_module("main")
        generated_app.app.dependency_overrides[generated_app.get_current_token] = lambda: {
            "sub": "user-1"
        }
        from fastapi.testclient import TestClient

        with TestClient(generated_app.app) as client:
            client.cookies.set("access_token", "provider-issued-token")
            response = client.get("/csrf")

        assert response.status_code == 200
        assert "secure" not in response.headers["set-cookie"].lower()
    finally:
        sys.path.remove(str(source_file.parent))
        sys.modules.pop("main", None)


@pytest.mark.parametrize(
    ("setting", "value", "error_message"),
    [
        ("APYRA_CSRF_SECRET", None, "APYRA_CSRF_SECRET"),
        ("APYRA_CSRF_SECRET", "short", "APYRA_CSRF_SECRET"),
        ("APYRA_COOKIE_SECURE", "sometimes", "APYRA_COOKIE_SECURE"),
    ],
)
def test_cookie_auth_template_rejects_invalid_environment_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: str | None,
    error_message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["new", "cookie_demo", "--template", "cookie-auth"]) == 0
    environment = os.environ.copy()
    environment["APYRA_CSRF_SECRET"] = "x" * 32
    environment.pop("APYRA_COOKIE_SECURE", None)
    if value is None:
        environment.pop(setting, None)
    else:
        environment[setting] = value
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=tmp_path / "cookie_demo",
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert error_message in result.stderr


def test_generators_create_expected_files(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["generate", "model", "User"]) == 0
        assert main(["generate", "router", "users"]) == 0
        assert main(["generate", "service", "User"]) == 0
        assert main(["generate", "schema", "User"]) == 0
        assert main(["generate", "repository", "User"]) == 0
        assert (tmp_path / "models" / "user.py").is_file()
        assert (tmp_path / "routers" / "users.py").is_file()
        assert (tmp_path / "services" / "user.py").is_file()
        assert (tmp_path / "schemas" / "user.py").is_file()
        repository = (tmp_path / "repositories" / "user.py").read_text()
        assert "from models.user import User" in repository
        assert "class UserRepository(Repository[User]):" in repository
        assert "super().__init__(session, User)" in repository
    finally:
        os.chdir(original)


def test_generators_do_not_overwrite(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["generate", "module", "users"]) == 0
        try:
            main(["generate", "module", "users"])
        except FileExistsError:
            pass
        else:
            raise AssertionError("expected FileExistsError")
    finally:
        os.chdir(original)


def test_crud_generator_creates_all_files(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["generate", "crud", "User"]) == 0
        assert (tmp_path / "models" / "user.py").is_file()
        assert (tmp_path / "schemas" / "user.py").is_file()
        assert (tmp_path / "repositories" / "user.py").is_file()
        assert (tmp_path / "services" / "user.py").is_file()
        assert (tmp_path / "routers" / "user.py").is_file()
    finally:
        os.chdir(original)


def test_crud_generator_checks_conflicts_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "schemas" / "user.py"
    existing.parent.mkdir()
    existing.write_text("custom schema\n")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        main(["generate", "crud", "User"])

    assert not (tmp_path / "models" / "user.py").exists()
    assert existing.read_text() == "custom schema\n"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["generate", "model", "User", "--dry-run"]) == 0
        assert not (tmp_path / "models" / "user.py").exists()
    finally:
        os.chdir(original)


@pytest.mark.parametrize(
    "args",
    [
        ["new", "../outside"],
        ["new", 'demo"\n[tool.uv]'],
        ["new", "demo..service"],
        ["generate", "module", "../outside", "--force"],
        ["generate", "module", "class"],
        ["generate", "model", "bad-name"],
    ],
)
def test_rejects_unsafe_names_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    with pytest.raises(SystemExit) as exc_info:
        main(args)

    assert exc_info.value.code == 2
    assert not (tmp_path / "outside").exists()
    assert not (tmp_path / "outside.py").exists()
    assert not (workspace / "outside.py").exists()
    assert not any(workspace.iterdir())
