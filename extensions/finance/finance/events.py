"""
Finance module event handlers.
Subscribes to cross-module events and creates appropriate financial entries.
"""
import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)


async def handle_order_confirmed(payload: BaseEventPayload):
    """
    Handles ORDER_CONFIRMED events from the Sales module.
    In a complete implementation, this would:
    1. Create an Accounts Receivable (AR) entry
    2. Create corresponding journal entry lines
    
    For now, this logs the event and serves as the wiring template.
    """
    order_id = payload.data.get("order_id")
    total_amount = payload.data.get("total_amount")
    customer_id = payload.data.get("customer_id")

    logger.info(
        f"[Finance] Received ORDER_CONFIRMED: order={order_id}, "
        f"amount={total_amount}, customer={customer_id}"
    )
    # TODO: Create AR journal entry when AR accounts are configured
    # This is the integration point between Sales and Finance


def register_event_handlers():
    """Registers all finance event handlers with the event bus."""
    event_bus.subscribe("ORDER_CONFIRMED", handle_order_confirmed)
    logger.info("[Finance] Event handlers registered: ORDER_CONFIRMED")
