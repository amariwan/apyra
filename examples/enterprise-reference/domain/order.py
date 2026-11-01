"""Order domain model."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from apyra.domain import Entity


class OrderStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"


class Order(Entity):
    def __init__(
        self,
        customer_id: str = "",
        status: OrderStatus = OrderStatus.CREATED,
        entity_id: UUID | None = None,
    ) -> None:
        super().__init__(entity_id)
        self.customer_id = customer_id
        self.status = status
