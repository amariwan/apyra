"""Apyra developer CLI."""

from __future__ import annotations

import argparse
import keyword
import re
from pathlib import Path

_COOKIE_AUTH_MAIN = """import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from apyra.core import Settings
from apyra.fastapi import create_app, get_current_token, require_csrf
from apyra.security import generate_csrf_token

csrf_secret = os.environ.get("APYRA_CSRF_SECRET", "")
if len(csrf_secret.encode("utf-8")) < 32:
    raise RuntimeError("APYRA_CSRF_SECRET must contain at least 32 UTF-8 bytes")

secure_setting = os.environ.get("APYRA_COOKIE_SECURE", "true").lower()
if secure_setting not in {"true", "false"}:
    raise RuntimeError("APYRA_COOKIE_SECURE must be 'true' or 'false'")
csrf_cookie_secure = secure_setting == "true"
csrf_dependency = require_csrf(csrf_secret, binding_cookie_name="access_token")

router = APIRouter()


@router.get("/csrf")
async def issue_csrf_token(
    request: Request,
    response: Response,
    _payload: dict[str, object] = Depends(get_current_token),
) -> dict[str, str]:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="missing_authorization")
    token = generate_csrf_token(csrf_secret, binding=access_token)
    response.set_cookie(
        "csrf_token",
        token,
        httponly=False,
        secure=csrf_cookie_secure,
        samesite="lax",
    )
    return {"csrf_token": token}


@router.post("/write")
async def write(
    _payload: dict[str, object] = Depends(get_current_token),
    _csrf: None = Depends(csrf_dependency),
) -> dict[str, bool]:
    return {"ok": True}


app = create_app(
    title="Apyra Cookie-Auth API",
    routers=[router],
    settings=Settings(api_prefix=""),
)
"""

_COOKIE_AUTH_README = """# {name}

Cookie-auth integration starter for Apyra.

## Configuration

- Set `APYRA_CSRF_SECRET` to a random secret with at least 32 UTF-8 bytes.
- Configure `AUTH_JWKS_URL`, `AUTH_ISSUER`, and `AUTH_AUDIENCE` for the identity provider
  whose validated access token is sent in the `access_token` cookie.
- The provider or your login integration must issue that cookie with appropriate `Secure`,
  `HttpOnly`, and `SameSite` attributes. This starter does not implement login or token issuance.
- `GET /csrf` returns a signed CSRF token and sets a script-readable `csrf_token` cookie.
  Send its value in the `X-CSRF-Token` header for unsafe requests such as `POST /write`.
- `APYRA_COOKIE_SECURE` defaults to `true`. Set it to `false` only for local HTTP development;
  never disable `Secure` in production.

CSRF does not replace Origin checks. Configure your own Origin policy and use HTTPS in deployed
environments. Cross-origin cookie authentication requires an explicit application CORS and cookie
policy.
"""


def _project_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*", value):
        raise argparse.ArgumentTypeError(
            "project name must use alphanumeric segments separated by '.', '_' or '-'"
        )
    return value


def _generator_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) or keyword.iskeyword(value):
        raise argparse.ArgumentTypeError("generator name must be a valid Python identifier")
    return value


def _write(path: Path, content: str, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _new_project(name: str, *, force: bool = False, template: str = "minimal") -> None:
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
    if template == "cookie-auth":
        main_content = _COOKIE_AUTH_MAIN
        readme_content = _COOKIE_AUTH_README.format(name=name)
    else:
        main_content = """from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app(title="Apyra API", routers=[router], settings=Settings(api_prefix="/api"))
"""
        readme_content = f"# {name}\n"
    _write(root / "main.py", main_content, force=force)
    _write(root / "README.md", readme_content, force=force)


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

from sqlalchemy.ext.asyncio import AsyncSession

from apyra.db import Repository
from models.{file_name} import {class_name}


class {class_name}Repository(Repository[{class_name}]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, {class_name})
''',
        force=force,
    )


def _generate_crud(name: str, *, force: bool = False) -> None:
    if not force:
        file_name = _snake(name)
        service_name = name.removesuffix("Service") if name.endswith("Service") else name
        paths = (
            Path("models") / f"{file_name}.py",
            Path("schemas") / f"{file_name}.py",
            Path("repositories") / f"{file_name}.py",
            Path("services") / f"{_snake(service_name)}.py",
            Path("routers") / f"{file_name}.py",
        )
        existing = next((path for path in paths if path.exists()), None)
        if existing is not None:
            raise FileExistsError(f"refusing to overwrite existing file: {existing}")

    _generate_model(name, force=force)
    _generate_schema(name, force=force)
    _generate_repository(name, force=force)
    _generate_service(name, force=force)
    _generate_router(name, force=force)


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the selected command, and return its exit status."""
    parser = argparse.ArgumentParser(prog="apyra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("name", type=_project_name)
    new_parser.add_argument("--force", action="store_true")
    new_parser.add_argument("--template", choices=("minimal", "cookie-auth"), default="minimal")

    generate_parser = subparsers.add_parser("generate")
    generate_subparsers = generate_parser.add_subparsers(dest="target", required=True)
    for target_name in ("module", "model", "router", "service", "schema", "repository", "crud"):
        target_parser = generate_subparsers.add_parser(target_name)
        target_parser.add_argument("name", type=_generator_name)
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
        _new_project(args.name, force=args.force, template=args.template)
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
        parser.error("database migration commands are not implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
