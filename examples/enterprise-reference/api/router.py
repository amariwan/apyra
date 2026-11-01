"""HTTP routes for the reference application."""

from __future__ import annotations

import os
from typing import Annotated, Any

import redis.asyncio as redis_async
from apyra.auth import TokenService
from apyra.fastapi import require_scopes
from apyra.messaging.contracts import MessageEnvelope
from apyra.messaging.idempotency import InMemoryIdempotencyStore
from apyra.messaging.outbox import OutboxRepository
from apyra.messaging.redis_streams import RedisStreamsConsumer, RedisStreamsPublisher
from apyra.workflow.engine import WorkflowEngine
from apyra.workflow.state import Workflow
from fastapi import APIRouter, Depends, HTTPException, Request

from domain.order import Order, OrderStatus
from infrastructure.database import create_session_manager
from infrastructure.repository import OrderRepository

router = APIRouter()
session_manager = create_session_manager()
idempotency_store = InMemoryIdempotencyStore()


def _token_service(request: Request) -> TokenService:
    return request.app.state.token_service  # type: ignore[no-any-return]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/token")
async def issue_token(customer_id: str, request: Request) -> dict[str, str]:
    service: TokenService = _token_service(request)
    pair = service.issue_token_pair(
        subject=customer_id, scopes=["orders:read", "orders:write"], access_expires_in=900
    )
    return {"access_token": pair.access_token, "token_type": "bearer"}


@router.post("/orders")
async def create_order(
    customer_id: str,
    request: Request,
    payload: Annotated[dict[str, Any], Depends(require_scopes("orders:write"))],
) -> dict[str, str]:
    async with session_manager.session() as session:
        repository = OrderRepository(session)
        outbox = OutboxRepository(session)

        order = Order(customer_id=customer_id, status=OrderStatus.CREATED)
        await repository.add(order)
        await outbox.add("order.created", {"order_id": str(order.id)})
        await session.commit()
        return {"order_id": str(order.id), "status": order.status.value}


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    payload: Annotated[dict[str, Any], Depends(require_scopes("orders:read"))],
) -> dict[str, str]:
    async with session_manager.session() as session:
        repository = OrderRepository(session)
        order = await repository.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="not_found")
        return {
            "order_id": str(order.id),
            "customer_id": order.customer_id,
            "status": order.status.value,
        }


@router.post("/orders/{order_id}/process")
async def process_order(
    order_id: str,
    payload: Annotated[dict[str, Any], Depends(require_scopes("orders:write"))],
) -> dict[str, str]:
    async def step(workflow: Any) -> str:
        async with session_manager.session() as session:
            repository = OrderRepository(session)
            order = await repository.get(order_id)
            if order is None:
                raise HTTPException(status_code=404, detail="not_found")
            order.status = OrderStatus.PROCESSING
            await session.commit()
            return order.status.value

    async with session_manager.session() as session:
        engine = WorkflowEngine(session)
        workflow = Workflow(name=f"process-order-{order_id}")
        await engine.start(workflow, [step])
        status = workflow.status.value
    return {"workflow_id": workflow.workflow_id, "status": status}


@router.post("/publish-pending")
async def publish_pending() -> dict[str, int]:
    async with session_manager.session() as session:
        outbox = OutboxRepository(session)
        claimed = await outbox.claim("publisher", 100, 30)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis_async.from_url(redis_url, decode_responses=True)
        publisher = RedisStreamsPublisher(client, stream="orders")
        for message in claimed:
            await publisher.publish(MessageEnvelope(message_id=message.id, payload=message.payload))
            await outbox.mark_delivered(message)
        await session.commit()
        await client.aclose()
        return {"published": len(claimed)}


@router.post("/consume")
async def consume_pending(max_messages: int = 10) -> dict[str, int]:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis_async.from_url(redis_url, decode_responses=True)
    processed = 0

    async def handler(envelope: MessageEnvelope, context: Any) -> None:
        nonlocal processed
        processed += 1

    handler_obj = type("H", (), {"handle": handler})()
    consumer = RedisStreamsConsumer(
        client,
        stream="orders",
        group="reference-consumers",
        consumer_name="consumer-1",
        handler=handler_obj,
        idempotency_store=idempotency_store,
        block_ms=100,
    )
    await consumer.ensure_group()
    import asyncio

    async def _run() -> None:
        await consumer.run()

    task = asyncio.create_task(_run())
    await asyncio.sleep(0.5)
    consumer.stop()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (TimeoutError, Exception):  # noqa: BLE001
        task.cancel()
    await client.aclose()
    return {"processed": processed}
