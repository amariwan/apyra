"""Database-backed Apyra FastAPI application (SQLite).

Demonstrates async SQLAlchemy sessions, the generic ``Repository``, and
auto-creation of tables on startup.

Development example only: its routes have no authentication or authorization.
Add route-level access controls before exposing it to untrusted clients.

Run with::

    uv run --project examples/database-api uvicorn main:app \
      --app-dir examples/database-api --reload
"""

from __future__ import annotations

import uuid
from typing import Annotated

from apyra.core import Settings
from apyra.db import Base, DatabaseSessionManager, Repository
from apyra.fastapi import create_app
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from fastapi import APIRouter, Depends, HTTPException

DB_URL = "sqlite+aiosqlite:///./example.db"


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)


manager = DatabaseSessionManager(DB_URL, engine_kwargs={"echo": False})


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with manager.session() as session:
        yield session  # type: ignore[misc]


class ItemIn(BaseModel):
    name: str


class ItemOut(BaseModel):
    id: str
    name: str


api = APIRouter()


@api.post("/items", response_model=ItemOut)
async def create_item(
    body: ItemIn, session: Annotated[AsyncSession, Depends(get_session)]
) -> ItemOut:
    repo = Repository(session, Item)
    item = await repo.create(name=body.name)
    await session.commit()
    return ItemOut(id=item.id, name=item.name)


@api.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> ItemOut:
    repo = Repository(session, Item)
    item = await repo.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return ItemOut(id=item.id, name=item.name)


@api.get("/items", response_model=list[ItemOut])
async def list_items(session: Annotated[AsyncSession, Depends(get_session)]) -> list[ItemOut]:
    repo = Repository(session, Item)
    items = await repo.list()
    return [ItemOut(id=i.id, name=i.name) for i in items]


async def _create_tables(app: object = None) -> None:  # noqa: ARG001
    await manager._ensure_current_loop()
    engine = manager.engine
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _shutdown(app: object = None) -> None:  # noqa: ARG001
    await manager.close()


app = create_app(
    title="Database Apyra API",
    routers=[api],
    settings=Settings(api_prefix="/api"),
    startup=[_create_tables],
    shutdown=[_shutdown],
)
