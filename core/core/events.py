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

        # Persist event to EventStore (best-effort — don't block emission)
        await self._persist_event(event_payload)

        handlers = self._subscribers.get(event_payload.event_type, [])
        if not handlers:
            logger.debug(f"No handlers found for event: {event_payload.event_type}")
            return

        handler_count = len(handlers)
        completed = 0
        errors = []

        async def safe_execute(handler: Callable, payload: BaseEventPayload):
            nonlocal completed
            try:
                await handler(payload)
                completed += 1
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Event handler {handler.__name__} failed for {payload.event_type}: {e}", exc_info=True)

        await asyncio.gather(*(safe_execute(handler, event_payload) for handler in handlers))

        # Update EventStore with processing result
        await self._update_event_status(
            event_payload.event_id,
            handler_count,
            completed,
            errors
        )

    async def _persist_event(self, payload: BaseEventPayload):
        """Persists the event to EventStore for audit trail and replay."""
        try:
            from .audit import EventStore
            from .database import get_session_maker

            session_maker = get_session_maker()
            async with session_maker() as session:
                event_record = EventStore(
                    id=payload.event_id,
                    event_type=payload.event_type,
                    emitter_module=payload.emitter_module,
                    correlation_id=payload.correlation_id,
                    payload=payload.data,
                    status="EMITTED",
                    handler_count=len(self._subscribers.get(payload.event_type, [])),
                )
                session.add(event_record)
                await session.commit()
        except Exception as e:
            logger.warning(f"Could not persist event {payload.event_type}: {e}")

    async def _update_event_status(self, event_id: uuid.UUID, total: int, completed: int, errors: list):
        """Updates the EventStore with processing results."""
        try:
            from .audit import EventStore
            from .database import get_session_maker
            from sqlmodel import select

            session_maker = get_session_maker()
            async with session_maker() as session:
                stmt = select(EventStore).where(EventStore.id == event_id)
                result = await session.execute(stmt)
                record = result.scalars().first()
                if record:
                    record.status = "PROCESSED" if completed == total else "FAILED"
                    record.handlers_completed = completed
                    record.processed_at = datetime.now(timezone.utc)
                    if errors:
                        record.error_message = "; ".join(errors)
                        record.status = "FAILED" if completed == 0 else "PARTIAL"
                    session.add(record)
                    await session.commit()
        except Exception as e:
            logger.warning(f"Could not update event status: {e}")

# Singleton instance
event_bus: AbstractEventBus = InMemoryEventBus()
