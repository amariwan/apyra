"""Order repository for the reference application."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.order import Order, OrderStatus
from infrastructure.models import OrderModel


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> None:
        self._session.add(
            OrderModel(id=str(order.id), customer_id=order.customer_id, status=order.status.value)
        )
        await self._session.flush()

    async def get(self, order_id: str) -> Order | None:
        result = await self._session.execute(select(OrderModel).where(OrderModel.id == order_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return Order(
            customer_id=model.customer_id,
            status=OrderStatus(model.status),
            entity_id=uuid.UUID(model.id),
        )
