import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)


async def handle_order_shipped(payload: BaseEventPayload):
    """
    Subscribes to SELL_ORDER_SHIPPED.
    Accrues stub cost of goods sold (COGS).
    """
    order_id = payload.data.get("order_id")
    logger.info(f"[Finance] Accrued stub COGS for shipped Order {order_id}")


def register_event_handlers():
    event_bus.subscribe("SELL_ORDER_SHIPPED", handle_order_shipped)
    logger.info("[Finance] Event handlers registered successfully")
