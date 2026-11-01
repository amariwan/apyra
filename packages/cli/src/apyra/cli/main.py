"""Apyra developer CLI."""

from __future__ import annotations

import argparse
import keyword
import re
from dataclasses import dataclass
from pathlib import Path

from .banner import print_banner, should_show_banner
from .templates import new_distributed, new_modular_monolith

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


@dataclass(frozen=True)
class FeatureSet:
    """Optional features enabled for a generated minimal project."""

    database: bool = False
    auth: bool = False
    cache: bool = False
    messaging: bool = False
    observability: bool = False

    @property
    def any_enabled(self) -> bool:
        return any(
            (
                self.database,
                self.auth,
                self.cache,
                self.messaging,
                self.observability,
            )
        )

    @classmethod
    def from_flags(
        cls,
        *,
        database: bool = False,
        auth: bool = False,
        cache: bool = False,
        messaging: bool = False,
        observability: bool = False,
        all_features: bool = False,
    ) -> FeatureSet:
        if all_features:
            database = auth = cache = messaging = observability = True
        return cls(
            database=database,
            auth=auth,
            cache=cache,
            messaging=messaging,
            observability=observability,
        )

    def dependency_lines(self) -> list[str]:
        lines = ['    "apyra-fastapi>=0.1.0,<0.2.0",']
        if self.database:
            lines.append('    "apyra-db[sqlite]>=0.1.0,<0.2.0",')
        if self.auth:
            lines.append('    "apyra-auth>=0.1.0,<0.2.0",')
        if self.cache:
            lines.append('    "apyra-cache>=0.1.0,<0.2.0",')
        if self.messaging:
            lines.append('    "apyra-messaging>=0.1.0,<0.2.0",')
        if self.observability:
            lines.append('    "apyra-observability>=0.1.0,<0.2.0",')
        return lines

    def build_minimal_main(self) -> str:
        imports: list[str] = ["from fastapi import APIRouter"]
        body_lines: list[str] = []

        if self.observability:
            imports.append("import os")
            imports.append("from apyra.observability import configure_logging")
            body_lines.append(
                'configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), json_output=True)'
            )
            body_lines.append("")

        imports.append("from apyra.core import Settings")

        if self.database:
            imports.append("from apyra.db import DatabaseManager")
            body_lines.append('database_manager = DatabaseManager("sqlite+aiosqlite:///./app.db")')
            body_lines.append("")

        if self.auth:
            imports.append("from apyra.auth import AuthSettings  # noqa: F401")
            body_lines.append(
                "# Configure AuthSettings from environment variables before serving requests."
            )
            body_lines.append("")

        if self.cache:
            imports.append("from apyra.cache import CacheSettings  # noqa: F401")
            body_lines.append("# Configure a cache adapter via CacheSettings when needed.")
            body_lines.append("")

        if self.messaging:
            imports.append("from apyra.messaging.contracts import MessageEnvelope  # noqa: F401")
            body_lines.append("# Messaging contracts are available for event-driven features.")
            body_lines.append("")

        imports.append("from apyra.fastapi import create_app")

        parts: list[str] = []
        parts.append('"""Application entry point generated by Apyra."""')
        parts.append("")
        parts.extend(imports)
        parts.append("")
        if body_lines:
            parts.extend(body_lines)
        parts.append("router = APIRouter()")
        parts.append("")
        parts.append("")
        parts.append('@router.get("/health")')
        parts.append("async def health() -> dict[str, str]:")
        parts.append('    return {"status": "ok"}')
        parts.append("")
        parts.append("")

        if self.database:
            parts.append("async def _startup(app: object) -> None:")
            parts.append("    pass")
            parts.append("")
            parts.append("")
            parts.append("async def _shutdown(app: object) -> None:")
            parts.append("    await database_manager.close()")
            parts.append("")
            parts.append("")
            parts.append("app = create_app(")
            parts.append('    title="Apyra API",')
            parts.append("    routers=[router],")
            parts.append('    settings=Settings(api_prefix="/api"),')
            parts.append("    startup=[_startup],")
            parts.append("    shutdown=[_shutdown],")
            parts.append(")")
        else:
            parts.append(
                'app = create_app(title="Apyra API", routers=[router], settings=Settings(api_prefix="/api"))'
            )

        parts.append("")
        return "\n".join(parts)


def _new_project(
    name: str,
    *,
    force: bool = False,
    template: str = "minimal",
    features: FeatureSet | None = None,
) -> None:
    if features is None:
        features = FeatureSet()

    root = Path(name)
    if root.exists() and not force:
        raise FileExistsError(f"project directory already exists: {root}")

    if template == "cookie-auth":
        main_content = _COOKIE_AUTH_MAIN
        readme_content = _COOKIE_AUTH_README.format(name=name)
        dependency_lines = ['    "apyra-fastapi>=0.1.0,<0.2.0",']
    elif template == "minimal":
        if features.any_enabled:
            main_content = features.build_minimal_main()
            dependency_lines = features.dependency_lines()
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
            dependency_lines = ['    "apyra-fastapi>=0.1.0,<0.2.0",']
        readme_content = f"# {name}\n"
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
        dependency_lines = ['    "apyra-fastapi>=0.1.0,<0.2.0",']
        readme_content = f"# {name}\n"

    pyproject = (
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
        "dependencies = [\n" + "\n".join(dependency_lines) + "\n]\n"
    )
    _write(root / "pyproject.toml", pyproject, force=force)
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

from apyra.db import Base
from sqlalchemy.orm import Mapped, mapped_column


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
from sqlalchemy.ext.asyncio import AsyncSession

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


def _generate_usecase(name: str, *, force: bool = False) -> None:
    class_name = name if name[0].isupper() else name.capitalize()
    if not class_name.endswith("UseCase"):
        class_name = f"{class_name}UseCase"
    base_name = name.removesuffix("UseCase") if name.endswith("UseCase") else name
    file_name = _snake(base_name)
    path = Path("usecases") / f"{file_name}.py"
    _write(
        path,
        f'''"""{class_name} use case."""

from __future__ import annotations

from apyra.application import UseCase


class {class_name}(UseCase):
    async def execute(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {{"ok": True}}
''',
        force=force,
    )


def _generate_resource(name: str, *, force: bool = False) -> None:
    file_name = _snake(name)
    class_name = name if name[0].isupper() else name.capitalize()
    service_name = name.removesuffix("Service") if name.endswith("Service") else name
    paths = (
        Path("models") / f"{file_name}.py",
        Path("schemas") / f"{file_name}.py",
        Path("repositories") / f"{file_name}.py",
        Path("services") / f"{_snake(service_name)}.py",
        Path("routers") / f"{file_name}.py",
        Path("usecases") / f"{file_name}.py",
        Path("tests") / f"test_{file_name}.py",
    )
    if not force:
        existing = next((path for path in paths if path.exists()), None)
        if existing is not None:
            raise FileExistsError(f"refusing to overwrite existing file: {existing}")

    _generate_model(name, force=True)
    _generate_schema(name, force=True)
    _generate_repository(name, force=True)
    _generate_service(name, force=True)
    _generate_router(name, force=True)
    _generate_usecase(name, force=True)
    _write(
        Path("tests") / f"test_{file_name}.py",
        f'''"""Tests for {file_name} resource."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.{file_name} import {class_name}Create, {class_name}Read


def test_{file_name}_schema_roundtrip() -> None:
    payload = {class_name}Create(name="example")
    assert payload.name == "example"
    reading = {class_name}Read(id=1, name=payload.name)
    assert reading.id == 1
    assert reading.name == payload.name
''',
        force=True,
    )

    main_path = Path("main.py")
    if not main_path.exists():
        _write(
            main_path,
            f'''"""Application entry point wiring the {name} resource."""

from __future__ import annotations

from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

from routers.{file_name} import router as resource_router

health_router = APIRouter()


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {{"status": "ok"}}


app = create_app(
    title="{name} API",
    routers=[health_router, resource_router],
    settings=Settings(api_prefix="/api"),
)
''',
        )
    # When main.py already exists, leave it untouched; wiring additional resources
    # into an existing composition root is the application author's responsibility.


""


def _run_doctor(*, json_output: bool = False) -> int:
    import json as _json
    import sys

    findings: list[dict[str, str]] = []

    def add(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    # Python version
    add("info", "python-version", f"Python {sys.version.split()[0]}")

    # Apyra packages
    apyra_modules = [
        "apyra.core",
        "apyra.fastapi",
        "apyra.db",
        "apyra.auth",
        "apyra.security",
        "apyra.cache",
        "apyra.observability",
        "apyra.messaging",
        "apyra.workflow",
        "apyra.application",
        "apyra.domain",
    ]
    for module_name in apyra_modules:
        try:
            module = __import__(module_name, fromlist=["*"])
            version = getattr(module, "__version__", "unknown")
            add("info", f"package:{module_name}", f"{module_name} {version} available")
        except Exception as exc:  # noqa: BLE001
            add("error", f"package:{module_name}", f"{module_name} import failed: {exc}")

    # Optional dependencies
    optional = {
        "fastapi": "apyra-fastapi",
        "sqlalchemy": "apyra-db",
        "redis": "apyra cache/messaging extras",
        "httpx": "apyra-ai / email providers",
        "boto3": "apyra-storage[s3]",
    }
    for module_name, hint in optional.items():
        try:
            __import__(module_name)
            add("info", f"optional:{module_name}", f"{module_name} available")
        except ModuleNotFoundError:
            add("warning", f"optional:{module_name}", f"{module_name} not installed ({hint})")

    # Docker availability
    import shutil as _shutil

    if _shutil.which("docker") is not None:
        add("info", "tool:docker", "docker available")
    else:
        add("warning", "tool:docker", "docker not found (optional for containerized workflows)")

    # Redis connectivity (best effort, read-only)
    import os as _os

    redis_url = _os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import asyncio as _asyncio

            import redis.asyncio as _redis_async

            async def _ping_redis() -> bool:
                from typing import Any

                client: Any = _redis_async.from_url(redis_url, decode_responses=True)
                try:
                    return bool(await client.ping())
                finally:
                    await client.aclose()

            if _asyncio.run(_ping_redis()):
                add("info", "redis:connectivity", "Redis reachable")
            else:
                add("warning", "redis:connectivity", "Redis ping returned false")
        except Exception as exc:  # noqa: BLE001
            add("warning", "redis:connectivity", f"Redis unreachable: {exc}")

    # Environment files
    for env_file in (".env", ".env.local", ".env.dev"):
        if Path(env_file).is_file():
            add("info", f"env:{env_file}", f"{env_file} present")
        else:
            add("info", f"env:{env_file}", f"{env_file} not found (optional)")

    # Security hints
    import os

    csrf_secret = os.environ.get("APYRA_CSRF_SECRET", "")
    if csrf_secret and len(csrf_secret.encode("utf-8")) < 32:
        add("warning", "security:csrf-secret", "APYRA_CSRF_SECRET is shorter than 32 bytes")
    jwt_secret = os.environ.get("AUTH_HS_SECRET", "")
    if jwt_secret and len(jwt_secret) < 32:
        add("warning", "security:jwt-secret", "AUTH_HS_SECRET looks short")

    if json_output:
        print(_json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding['message']}")

    has_error = any(f["severity"] == "error" for f in findings)
    return 1 if has_error else 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the selected command, and return its exit status."""
    parser = argparse.ArgumentParser(prog="apyra")
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable the startup banner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("name", nargs="?", type=_project_name, default=None)
    new_parser.add_argument("--force", action="store_true")
    new_parser.add_argument(
        "--template",
        choices=("minimal", "cookie-auth", "modular-monolith", "distributed"),
        default="minimal",
    )
    new_parser.add_argument("--interactive", "-i", action="store_true")
    new_parser.add_argument("--dry-run", action="store_true")
    new_parser.add_argument(
        "--with-db", action="store_true", help="Enable database support in the minimal template"
    )
    new_parser.add_argument(
        "--with-auth",
        action="store_true",
        help="Enable authentication support in the minimal template",
    )
    new_parser.add_argument(
        "--with-cache", action="store_true", help="Enable cache support in the minimal template"
    )
    new_parser.add_argument(
        "--with-messaging",
        action="store_true",
        help="Enable messaging support in the minimal template",
    )
    new_parser.add_argument(
        "--with-observability",
        action="store_true",
        help="Enable observability support in the minimal template",
    )
    new_parser.add_argument(
        "--all-features",
        action="store_true",
        help="Enable all optional features in the minimal template",
    )

    generate_parser = subparsers.add_parser("generate")
    generate_subparsers = generate_parser.add_subparsers(dest="target", required=True)
    for target_name in (
        "module",
        "model",
        "router",
        "service",
        "schema",
        "repository",
        "crud",
        "resource",
        "usecase",
    ):
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

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)

    if should_show_banner(
        no_banner=args.no_banner,
        json_output=bool(getattr(args, "json_output", False)),
    ):
        print_banner()

    if args.command == "new":
        if args.name is None:
            if args.interactive:
                try:
                    name = input("Project name [apyra-api]: ").strip() or "apyra-api"
                except EOFError:
                    name = "apyra-api"
                args.name = _project_name(name)
            else:
                parser.error("the following arguments are required: name")
        template = args.template
        features = FeatureSet.from_flags(
            database=getattr(args, "with_db", False),
            auth=getattr(args, "with_auth", False),
            cache=getattr(args, "with_cache", False),
            messaging=getattr(args, "with_messaging", False),
            observability=getattr(args, "with_observability", False),
            all_features=getattr(args, "all_features", False),
        )
        if args.interactive and not args.dry_run:
            try:
                choice = (
                    input(
                        "Template (minimal/cookie-auth/modular-monolith/distributed) [minimal]: "
                    ).strip()
                    or "minimal"
                )
            except EOFError:
                choice = "minimal"
            if choice in {"minimal", "cookie-auth", "modular-monolith", "distributed"}:
                template = choice
            if template == "minimal" and not features.any_enabled:
                try:
                    toggles = input(
                        "Enable features (db,auth,cache,messaging,observability) [none]: "
                    ).strip()
                except EOFError:
                    toggles = ""
                if toggles:
                    selected = {part.strip().lower() for part in toggles.split(",") if part.strip()}
                    features = FeatureSet(
                        database="db" in selected or "database" in selected,
                        auth="auth" in selected,
                        cache="cache" in selected,
                        messaging="messaging" in selected,
                        observability="observability" in selected or "obs" in selected,
                    )
        if args.dry_run:
            feature_suffix = ""
            if template == "minimal" and features.any_enabled:
                feature_suffix = f" features={','.join(f for f in ('db' if features.database else '', 'auth' if features.auth else '', 'cache' if features.cache else '', 'messaging' if features.messaging else '', 'observability' if features.observability else '') if f)}"
            print(f"would create project {args.name} (template={template}){feature_suffix}")
            return 0
        if template == "modular-monolith":
            new_modular_monolith(args.name, force=args.force)
        elif template == "distributed":
            new_distributed(args.name, force=args.force)
        else:
            _new_project(args.name, force=args.force, template=template, features=features)
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
        elif args.target == "resource":
            _generate_resource(args.name, force=args.force)
        elif args.target == "usecase":
            _generate_usecase(args.name, force=args.force)
        print(f"generated {args.target}: {args.name}")
        return 0
    if args.command == "check":
        print(args.message)
        return 0
    if args.command == "doctor":
        return _run_doctor(json_output=args.json_output)
    if args.command == "db":
        parser.error("database migration commands are not implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
