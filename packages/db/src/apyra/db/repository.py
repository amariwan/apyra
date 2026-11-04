"""Generic async repository utilities."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Generic, TypeVar, cast
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from .base import Base

ModelT = TypeVar("ModelT", bound=Base)
type CursorValue = str | int | float | bool | None | date | datetime | Decimal | UUID | bytes
_MAX_CURSOR_LENGTH = 16_384


def _identity_sequence_values(identity: Any) -> list[Any]:
    return [identity[index] for index in range(len(identity))]


@dataclass(slots=True)
class Page[ModelT: Base]:
    """A page of repository results with total count and offset metadata."""

    items: list[ModelT]
    total: int
    limit: int
    offset: int


@dataclass(slots=True)
class CursorPage[ModelT: Base]:
    """A cursor-paginated result and its continuation state."""

    items: list[ModelT]
    next_cursor: str | None
    has_more: bool


class Repository(Generic[ModelT]):  # noqa: UP046
    """Run common async queries and persistence operations for one model."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[ModelT],
        *,
        default_scope: Callable[[Any], Any] | None = None,
    ) -> None:
        self.session = session
        self.model = model
        self._default_scope = default_scope

    def _apply_scope(self, statement: Any, scope: Callable[[Any], Any] | None) -> Any:
        if self._default_scope is not None:
            statement = self._default_scope(statement)
        if scope is not None:
            statement = scope(statement)
        return statement

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
        """Return the model with this primary key, or ``None`` if absent.

        When a ``default_scope`` is configured (for example a tenant filter), the
        lookup is restricted by that scope so out-of-scope rows are never returned.
        """
        if self._default_scope is None:
            return await self.session.get(self.model, item_id)
        primary_key = list(self.model.__mapper__.primary_key)
        identity_values: list[Any]
        if len(primary_key) == 1 and not isinstance(item_id, (tuple, list, dict)):
            identity_values = [item_id]
        elif isinstance(item_id, dict):
            try:
                identity_values = [item_id[column.key] for column in primary_key]
            except KeyError as exc:
                raise ValueError("identity is missing a primary-key column") from exc
        elif isinstance(item_id, (tuple, list)):
            identity_values = _identity_sequence_values(item_id)
            if len(identity_values) != len(primary_key):
                raise ValueError("identity does not match the model primary key")
        else:
            raise ValueError("identity does not match the model primary key")
        statement = select(self.model).where(
            *(column == value for column, value in zip(primary_key, identity_values, strict=True))
        )
        statement = self._apply_scope(statement, None)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def count(
        self, *, filters: dict[str, object] | None = None, scope: Callable[[Any], Any] | None = None
    ) -> int:
        """Count matching rows after filters and an optional statement scope."""
        statement = select(func.count()).select_from(self.model)
        statement = self._apply_filters(statement, filters)
        statement = self._apply_scope(statement, scope)
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
        """Return filtered, ordered rows within the requested offset window."""
        statement = select(self.model)
        statement = self._apply_filters(statement, filters)
        statement = self._apply_scope(statement, scope)
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
        """Return an offset page and the total number of matching rows."""
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
        """Return a stable cursor page ordered by a column and primary key."""
        if limit < 1:
            return CursorPage(items=[], next_cursor=None, has_more=False)

        column = getattr(self.model, order_by)
        primary_key = list(self.model.__mapper__.primary_key)
        if not primary_key:
            raise ValueError("cursor pagination requires a primary key")
        primary_key_names: list[str] = []
        for key in primary_key:
            if key.key is None:
                raise ValueError("cursor pagination requires named primary-key columns")
            primary_key_names.append(key.key)
        ordering = [column] + [
            getattr(self.model, key_name)
            for key_name in primary_key_names
            if key_name != column.key
        ]
        statement = select(self.model)
        statement = self._apply_filters(statement, filters)
        statement = self._apply_scope(statement, scope)
        if cursor is not None:
            try:
                values = _decode_cursor(cursor)
            except TypeError as exc:
                raise ValueError("cursor is invalid") from exc
            if len(values) != len(ordering):
                raise ValueError("cursor does not match the requested ordering")
            comparisons: list[ColumnElement[bool]] = []
            for index, key in enumerate(ordering):
                prior_keys: list[ColumnElement[bool]] = [
                    cast(ColumnElement[bool], ordering[prior] == values[prior])
                    for prior in range(index)
                ]
                if values[index] is None:
                    comparison: ColumnElement[bool] = false()
                else:
                    comparison = cast(
                        ColumnElement[bool],
                        key < values[index] if descending else key > values[index],
                    )
                    if index == 0:
                        comparison = or_(comparison, key.is_(None))
                comparisons.append(and_(*prior_keys, comparison) if prior_keys else comparison)
            statement = statement.where(or_(*comparisons))
        statement = statement.order_by(
            *(key.desc().nulls_last() if descending else key.asc().nulls_last() for key in ordering)
        )
        statement = statement.limit(limit + 1)
        result = await self.session.execute(statement)
        items = list(result.scalars().all())
        has_more = len(items) > limit
        items = items[:limit]
        next_cursor = None
        if has_more and items:
            next_cursor = _encode_cursor([getattr(items[-1], key.key) for key in ordering])
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def create(self, **values: Any) -> ModelT:
        """Add a model with the supplied values and flush the session."""
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **values: Any) -> ModelT:
        """Assign values to a model and flush the session."""
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Delete a model and flush the session."""
        await self.session.delete(instance)
        await self.session.flush()


class TenantScopedRepository(Repository[ModelT]):
    """Repository that automatically restricts every query to one tenant.

    The model must include a ``tenant_id`` column (use
    :class:`apyra.db.TenantScopedMixin`). Every read, count, and paginate operation
    is filtered by the configured tenant id, so cross-tenant reads fail closed
    without relying on callers to remember a tenant filter.
    """

    def __init__(self, session: AsyncSession, model: type[ModelT], tenant_id: str) -> None:
        self.tenant_id = tenant_id
        tenant_column = cast(Any, model).tenant_id

        def tenant_scope(statement: Any) -> Any:
            return statement.where(tenant_column == tenant_id)

        super().__init__(session, model, default_scope=tenant_scope)

    async def create(self, **values: Any) -> ModelT:
        requested_tenant = values.setdefault("tenant_id", self.tenant_id)
        if requested_tenant != self.tenant_id:
            raise ValueError("cannot create a record for another tenant")
        return await super().create(**values)

    async def update(self, instance: ModelT, **values: Any) -> ModelT:
        await self._require_tenant_owner(instance)
        requested_tenant = values.get("tenant_id", self.tenant_id)
        if requested_tenant != self.tenant_id:
            raise ValueError("cannot move a record to another tenant")
        return await super().update(instance, **values)

    async def delete(self, instance: ModelT) -> None:
        await self._require_tenant_owner(instance)
        await super().delete(instance)

    async def _require_tenant_owner(self, instance: ModelT) -> None:
        if getattr(instance, "tenant_id", None) != self.tenant_id:
            raise ValueError("cannot modify a record owned by another tenant")

        state = sa_inspect(instance)
        identity = state.identity
        if identity is None:
            raise ValueError("cannot modify an unpersisted tenant record")

        identity_predicates = [
            primary_key == value
            for primary_key, value in zip(state.mapper.primary_key, identity, strict=True)
        ]
        tenant_column = cast(Any, self.model).tenant_id
        with self.session.no_autoflush:
            persisted_tenant = await self.session.scalar(
                select(tenant_column).where(and_(*identity_predicates)).with_for_update()
            )
        if persisted_tenant != self.tenant_id:
            raise ValueError("cannot modify a record no longer owned by this tenant")


def _encode_cursor(values: list[object]) -> str:
    payload = json.dumps(
        [_encode_cursor_value(value) for value in values], separators=(",", ":"), allow_nan=False
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _encode_cursor_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("cursor values must be finite")
        return value
    if isinstance(value, datetime):
        return {"__apyra_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__apyra_type__": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("cursor values must be finite")
        return {"__apyra_type__": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"__apyra_type__": "uuid", "value": str(value)}
    if isinstance(value, bytes):
        return {
            "__apyra_type__": "bytes",
            "value": base64.urlsafe_b64encode(value).decode("ascii"),
        }
    raise TypeError(f"unsupported cursor value type: {type(value).__name__}")


def _decode_cursor(value: str) -> list[CursorValue]:
    if len(value) > _MAX_CURSOR_LENGTH:
        raise ValueError("cursor is invalid")
    padding = "=" * (-len(value) % 4)
    try:
        payload = base64.b64decode((value + padding).encode("ascii"), altchars=b"-_", validate=True)
        decoded: object = json.loads(payload.decode("utf-8"))
    except (binascii.Error, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("cursor is invalid") from exc
    if not isinstance(decoded, list):
        raise TypeError("cursor must encode an ordered list of values")
    values: list[CursorValue] = []
    for item in cast(list[object], decoded):
        values.append(_decode_cursor_value(item))
    return values


def _decode_cursor_value(value: object) -> CursorValue:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    if isinstance(value, dict):
        item = cast(dict[str, object], value)
        if set(item) != {"__apyra_type__", "value"} or not isinstance(item["value"], str):
            raise ValueError("cursor values must be scalar")
        kind = item["__apyra_type__"]
        encoded = item["value"]
        try:
            if kind == "datetime":
                return datetime.fromisoformat(encoded)
            if kind == "date":
                return date.fromisoformat(encoded)
            if kind == "decimal":
                number = Decimal(encoded)
                if number.is_finite():
                    return number
            if kind == "uuid":
                return UUID(encoded)
            if kind == "bytes":
                return base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, InvalidOperation, UnicodeError, binascii.Error) as exc:
            raise ValueError("cursor value is invalid") from exc
    raise ValueError("cursor values must be scalar")
