import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)

async def emit_entity_created(entity_id: str, entity_name: str):
    payload = BaseEventPayload(
        emitter_module="sales",
        event_type="SALES_ENTITY_CREATED",
        data={"entity_id": entity_id, "name": entity_name}
    )
    await event_bus.emit(payload)

async def emit_customer_created(customer_id: str, customer_name: str):
    payload = BaseEventPayload(
        emitter_module="sales",
        event_type="CUSTOMER_CREATED",
        data={"customer_id": customer_id, "customer_name": customer_name}
    )
    await event_bus.emit(payload)

async def emit_customer_credit_hold(customer_id: str, customer_name: str, order_id: str, order_amount: float, available_credit: float):
    payload = BaseEventPayload(
        emitter_module="sales",
        event_type="CUSTOMER_CREDIT_HOLD",
        data={
            "customer_id": customer_id,
            "customer_name": customer_name,
            "order_id": order_id,
            "order_amount": order_amount,
            "available_credit": available_credit
        }
    )
    await event_bus.emit(payload)

async def emit_customer_credit_released(customer_id: str, customer_name: str, order_id: str, authorizer_name: str):
    payload = BaseEventPayload(
        emitter_module="sales",
        event_type="CUSTOMER_CREDIT_RELEASED",
        data={
            "customer_id": customer_id,
            "customer_name": customer_name,
            "order_id": order_id,
            "authorizer_name": authorizer_name
        }
    )
    await event_bus.emit(payload)

def register_event_handlers():
    logger.info("[Sales] Event handlers registered")
