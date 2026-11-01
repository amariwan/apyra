"""Create order use case."""

from __future__ import annotations

from domain.order import Order, OrderStatus


class CreateOrderUseCase:
    async def execute(self, customer_id: str) -> Order:
        return Order(customer_id=customer_id, status=OrderStatus.CREATED)
