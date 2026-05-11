"""
Sales module event emitters.
Emits events for cross-module integration (e.g., Sales → Finance).
"""
import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)


async def emit_order_confirmed(order_id: str, total_amount: str, customer_id: str):
    """Emits an ORDER_CONFIRMED event for the Finance module (and any other subscribers)."""
    payload = BaseEventPayload(
        emitter_module="sales",
        event_type="ORDER_CONFIRMED",
        data={
            "order_id": order_id,
            "total_amount": total_amount,
            "customer_id": customer_id,
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Sales] Emitted ORDER_CONFIRMED for order {order_id}")
