import os
from pathlib import Path

from apyra.cli.main import main


def test_new_project_creates_files(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["new", "demo"]) == 0
        assert (tmp_path / "demo" / "main.py").is_file()
        assert (tmp_path / "demo" / "pyproject.toml").is_file()
    finally:
        os.chdir(original)


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
        assert (tmp_path / "repositories" / "user.py").is_file()
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


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["generate", "model", "User", "--dry-run"]) == 0
        assert not (tmp_path / "models" / "user.py").exists()
    finally:
        os.chdir(original)
