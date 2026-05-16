import logging
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)


async def emit_finance_record_created(record_id: str, name: str):
    payload = BaseEventPayload(
        emitter_module="finance",
        event_type="FINANCE_RECORD_CREATED",
        data={"record_id": record_id, "name": name}
    )
    await event_bus.emit(payload)


def register_event_handlers():
    # Subscribe to events from other modules
    # event_bus.subscribe("SOME_EVENT", handler_function)
    logger.info("[Finance] Event handlers registered")
