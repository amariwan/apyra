"""Apyra developer CLI."""

from __future__ import annotations

import argparse
from pathlib import Path


def _write(path: Path, content: str, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _new_project(name: str, *, force: bool = False) -> None:
    root = Path(name)
    if root.exists() and not force:
        raise FileExistsError(f"project directory already exists: {root}")
    _write(
        root / "pyproject.toml",
        f'''[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["apyra-fastapi>=0.1.0,<0.2.0"]
''',
        force=force,
    )
    _write(
        root / "main.py",
        """from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app(title="Apyra API", routers=[router], settings=Settings(api_prefix="/api"))
""",
        force=force,
    )
    _write(root / "README.md", f"# {name}\n", force=force)


def _snake(name: str) -> str:
    result: list[str] = []
    for char in name:
        if char.isupper() and result:
            result.append("_")
        result.append(char.lower())
    return "".join(result).replace("-", "_")


def _generate_module(name: str, *, force: bool = False) -> None:
    path = Path("modules") / f"{name}.py"
    _write(
        path,
        f'''"""Module {name}."""


def register() -> str:
    return "{name}"
''',
        force=force,
    )


def _generate_model(name: str, *, force: bool = False) -> None:
    class_name = name if name[0].isupper() else name.capitalize()
    file_name = _snake(name)
    path = Path("models") / f"{file_name}.py"
    _write(
        path,
        f"""\"""{class_name} model.\""\"

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from apyra.db import Base


class {class_name}(Base):
    __tablename__ = "{file_name}s"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
""",
        force=force,
    )


def _generate_router(name: str, *, force: bool = False) -> None:
    module_name = _snake(name)
    class_name = module_name.replace("_", " ").title().replace(" ", "")
    path = Path("routers") / f"{module_name}.py"
    _write(
        path,
        f"""\"""{class_name} router.\""\"

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/{module_name}", tags=["{module_name}"])


@router.get("/")
async def list_{module_name}() -> list[dict[str, str]]:
    return []
""",
        force=force,
    )


def _generate_service(name: str, *, force: bool = False) -> None:
    class_name = name if name[0].isupper() else name.capitalize()
    if not class_name.endswith("Service"):
        class_name = f"{class_name}Service"
    file_name = _snake(name.removesuffix("Service") if name.endswith("Service") else name)
    path = Path("services") / f"{file_name}.py"
    _write(
        path,
        f"""\"""{class_name}.\""\"

from __future__ import annotations


class {class_name}:
    async def get(self, item_id: int) -> dict[str, int]:
        return {{"id": item_id}}
""",
        force=force,
    )


def _generate_schema(name: str, *, force: bool = False) -> None:
    class_name = name if name[0].isupper() else name.capitalize()
    file_name = _snake(name)
    path = Path("schemas") / f"{file_name}.py"
    _write(
        path,
        f'''"""{class_name} schemas."""

from __future__ import annotations

from pydantic import BaseModel


class {class_name}Create(BaseModel):
    name: str


class {class_name}Read({class_name}Create):
    id: int
''',
        force=force,
    )


def _generate_repository(name: str, *, force: bool = False) -> None:
    class_name = name if name[0].isupper() else name.capitalize()
    file_name = _snake(name)
    path = Path("repositories") / f"{file_name}.py"
    _write(
        path,
        f'''"""{class_name} repository."""

from __future__ import annotations

from apyra.db import Repository


class {class_name}Repository(Repository):
    pass
''',
        force=force,
    )


def _generate_crud(name: str, *, force: bool = False) -> None:
    _generate_model(name, force=force)
    _generate_schema(name, force=force)
    _generate_repository(name, force=force)
    _generate_service(name, force=force)
    _generate_router(name, force=force)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apyra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("name")
    new_parser.add_argument("--force", action="store_true")

    generate_parser = subparsers.add_parser("generate")
    generate_subparsers = generate_parser.add_subparsers(dest="target", required=True)
    for target_name in ("module", "model", "router", "service", "schema", "repository", "crud"):
        target_parser = generate_subparsers.add_parser(target_name)
        target_parser.add_argument("name")
        target_parser.add_argument("--force", action="store_true")
        target_parser.add_argument("--dry-run", action="store_true")

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--message", default="ok")

    db_parser = subparsers.add_parser("db")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)
    revision_parser = db_subparsers.add_parser("revision")
    revision_parser.add_argument("-m", "--message", default="revision")
    db_subparsers.add_parser("upgrade")

    args = parser.parse_args(argv)

    if args.command == "new":
        _new_project(args.name, force=args.force)
        print(f"created project {args.name}")
        return 0
    if args.command == "generate":
        if args.dry_run:
            print(f"would generate {args.target}: {args.name}")
            return 0
        if args.target == "module":
            _generate_module(args.name, force=args.force)
        elif args.target == "model":
            _generate_model(args.name, force=args.force)
        elif args.target == "router":
            _generate_router(args.name, force=args.force)
        elif args.target == "service":
            _generate_service(args.name, force=args.force)
        elif args.target == "schema":
            _generate_schema(args.name, force=args.force)
        elif args.target == "repository":
            _generate_repository(args.name, force=args.force)
        elif args.target == "crud":
            _generate_crud(args.name, force=args.force)
        print(f"generated {args.target}: {args.name}")
        return 0
    if args.command == "check":
        print(args.message)
        return 0
    if args.command == "db":
        if args.db_command == "revision":
            print(f"revision: {args.message}")
            return 0
        if args.db_command == "upgrade":
            print("upgrade requested")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
