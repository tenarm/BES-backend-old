import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)


async def handle_order_confirmed(payload: BaseEventPayload):
    """
    Subscribes to SELL_ORDER_CONFIRMED.
    Stubs inventory stock reservation.
    """
    order_id = payload.data.get("order_id")
    logger.info(f"[Inventory] Stub reserved stock for Order {order_id}")


def register_event_handlers():
    event_bus.subscribe("SELL_ORDER_CONFIRMED", handle_order_confirmed)
    logger.info("[Inventory] Event handlers registered successfully")
