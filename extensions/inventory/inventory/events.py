import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)

async def emit_entity_created(entity_id: str, entity_name: str):
    payload = BaseEventPayload(
        emitter_module="inventory",
        event_type="INVENTORY_ENTITY_CREATED",
        data={"entity_id": entity_id, "name": entity_name}
    )
    await event_bus.emit(payload)

def register_event_handlers():
    logger.info("[Inventory] Event handlers registered")
