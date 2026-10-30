"""Generic async repository utilities."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(slots=True)
class Page[ModelT: Base]:
    items: list[ModelT]
    total: int
    limit: int
    offset: int


@dataclass(slots=True)
class CursorPage[ModelT: Base]:
    items: list[ModelT]
    next_cursor: str | None
    has_more: bool


class Repository(Generic[ModelT]):  # noqa: UP046
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def _apply_filters(self, statement: Any, filters: dict[str, object] | None) -> Any:
        if not filters:
            return statement
        for field_name, value in filters.items():
            column = getattr(self.model, field_name)
            statement = statement.where(column == value)
        return statement

    def _apply_ordering(self, statement: Any, order_by: str | None, *, descending: bool) -> Any:
        if order_by is None:
            return statement
        column = getattr(self.model, order_by)
        if descending:
            return statement.order_by(column.desc())
        return statement.order_by(column.asc())

    async def get(self, item_id: Any) -> ModelT | None:
        return await self.session.get(self.model, item_id)

    async def count(
        self, *, filters: dict[str, object] | None = None, scope: Callable[[Any], Any] | None = None
    ) -> int:
        statement = select(func.count()).select_from(self.model)
        statement = self._apply_filters(statement, filters)
        if scope is not None:
            statement = scope(statement)
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def list(
        self,
        *,
        filters: dict[str, object] | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int = 100,
        offset: int = 0,
        scope: Callable[[Any], Any] | None = None,
    ) -> list[ModelT]:
        statement = select(self.model)
        statement = self._apply_filters(statement, filters)
        if scope is not None:
            statement = scope(statement)
        statement = self._apply_ordering(statement, order_by, descending=descending)
        statement = statement.limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def page(
        self,
        *,
        filters: dict[str, object] | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int = 100,
        offset: int = 0,
        scope: Callable[[Any], Any] | None = None,
    ) -> Page[ModelT]:
        items = await self.list(
            filters=filters,
            order_by=order_by,
            descending=descending,
            limit=limit,
            offset=offset,
            scope=scope,
        )
        total = await self.count(filters=filters, scope=scope)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def paginate(
        self,
        *,
        cursor: str | None = None,
        limit: int = 100,
        order_by: str = "id",
        descending: bool = False,
        filters: dict[str, object] | None = None,
        scope: Callable[[Any], Any] | None = None,
    ) -> CursorPage[ModelT]:
        if limit < 1:
            return CursorPage(items=[], next_cursor=None, has_more=False)

        column = getattr(self.model, order_by)
        statement = select(self.model)
        statement = self._apply_filters(statement, filters)
        if scope is not None:
            statement = scope(statement)
        if cursor is not None:
            value = _decode_cursor(cursor)
            if descending:
                statement = statement.where(column < value)
            else:
                statement = statement.where(column > value)
        statement = self._apply_ordering(statement, order_by, descending=descending)
        statement = statement.limit(limit + 1)
        result = await self.session.execute(statement)
        items = list(result.scalars().all())
        has_more = len(items) > limit
        items = items[:limit]
        next_cursor = None
        if has_more and items:
            next_cursor = _encode_cursor(getattr(items[-1], order_by))
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **values: Any) -> ModelT:
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()


def _encode_cursor(value: object) -> str:
    payload = json.dumps(value, default=str, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> object:
    padding = "=" * (-len(value) % 4)
    payload = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    return json.loads(payload.decode("utf-8"))
