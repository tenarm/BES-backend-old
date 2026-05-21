import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Awaitable, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Typed Payloads ---
class BaseEventPayload(BaseModel):
    """
    Standard envelope for all inter-module events.
    Ensures type safety, correlation tracking, and standard metadata.
    """
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    emitter_module: str
    event_type: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None  # Links to originating request chain

# --- Future-Proof Interface ---
class AbstractEventBus(ABC):
    """
    Abstract interface for the Event Bus.
    Allows seamless swapping from InMemory to Redis/RabbitMQ in Day 2.
    """
    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[BaseEventPayload], Awaitable[None]]):
        pass

    @abstractmethod
    async def emit(self, event_payload: BaseEventPayload):
        pass

# --- Resilient In-Memory Implementation with Event Persistence ---
class InMemoryEventBus(AbstractEventBus):
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[BaseEventPayload], Awaitable[None]]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[BaseEventPayload], Awaitable[None]]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Handler {handler.__name__} subscribed to {event_type}")

    async def emit(self, event_payload: BaseEventPayload):
        # Auto-inject correlation ID from request context if not provided
        if not event_payload.correlation_id:
            try:
                from .middleware import correlation_id_context
                event_payload.correlation_id = correlation_id_context.get()
            except Exception:
                pass

        # Trigger notification service asynchronously
        try:
            from .notifications import NotificationService
            asyncio.create_task(NotificationService.process_event_notifications(event_payload))
        except Exception as e:
            logger.error(f"Failed to trigger NotificationService for event {event_payload.event_type}: {e}")

        handlers = self._subscribers.get(event_payload.event_type, [])
        if not handlers:
            logger.debug(f"No handlers found for event: {event_payload.event_type}")

        handler_count = len(handlers)
        completed = 0
        errors: list[str] = []

        async def safe_execute(handler: Callable, payload: BaseEventPayload):
            nonlocal completed
            try:
                await handler(payload)
                completed += 1
            except Exception as e:
                errors.append(str(e))
                logger.error(
                    f"Event handler {handler.__name__} failed for "
                    f"{payload.event_type}: {e}", exc_info=True
                )

        if handlers:
            await asyncio.gather(*(safe_execute(h, event_payload) for h in handlers))

        # Fix #6: Single DB session after handlers complete — was previously
        # two sessions (persist on EMITTED + update status after handlers).
        # Now we know the final outcome before touching the DB.
        await self._persist_and_update_event(event_payload, handler_count, completed, errors)

    async def _persist_and_update_event(
        self,
        payload: BaseEventPayload,
        handler_count: int,
        completed: int,
        errors: list[str],
    ):
        """
        Persists the event to EventStore with its final status in ONE session.

        Fix #6: Replaces the former _persist_event() + _update_event_status()
        pair which opened two separate DB connections per event. Running handlers
        first means we can write the definitive status in a single commit.
        """
        try:
            from .audit import EventStore
            from .database import get_session_maker

            if errors and completed == 0:
                status = "FAILED"
            elif errors:
                status = "PARTIAL"
            elif handler_count > 0:
                status = "PROCESSED"
            else:
                status = "EMITTED"  # No subscribers — event recorded but unhandled

            session_maker = get_session_maker()
            async with session_maker() as session:
                event_record = EventStore(
                    id=payload.event_id,
                    event_type=payload.event_type,
                    emitter_module=payload.emitter_module,
                    correlation_id=payload.correlation_id,
                    payload=payload.data,
                    status=status,
                    handler_count=handler_count,
                    handlers_completed=completed,
                    processed_at=datetime.now(timezone.utc),
                    error_message="; ".join(errors) if errors else None,
                )
                session.add(event_record)
                await session.commit()
        except Exception as e:
            logger.warning(f"Could not persist event {payload.event_type}: {e}")


# Singleton instance
event_bus: AbstractEventBus = InMemoryEventBus()
