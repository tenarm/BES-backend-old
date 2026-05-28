import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Awaitable, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event payload envelope
# ---------------------------------------------------------------------------

class BaseEventPayload(BaseModel):
    """
    Standard envelope for all inter-module events.

    Provides type safety, correlation tracking, and consistent metadata across
    every event emitted on the bus.

    Attributes:
        event_id:       Unique identifier for this event instance.
        timestamp:      UTC time the event was created.
        emitter_module: The module that published the event (e.g. ``"sales"``).
        event_type:     UPPER_SNAKE_CASE event name (e.g. ``"SELL_ORDER_CONFIRMED"``).
        data:           Arbitrary event-specific payload dictionary.
        correlation_id: Propagated from the originating HTTP request's ``X-Request-ID``
                        header for end-to-end traceability.
    """
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    emitter_module: str
    event_type: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Abstract interface — swap InMemory → Redis/RabbitMQ without changing callers
# ---------------------------------------------------------------------------

class AbstractEventBus(ABC):
    """
    Abstract event bus interface.

    Concrete implementations must support at minimum synchronous subscription
    and asynchronous event emission.
    """

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[BaseEventPayload], Awaitable[None]]):
        """Registers ``handler`` to be called whenever ``event_type`` is emitted."""

    @abstractmethod
    async def emit(self, event_payload: BaseEventPayload):
        """Publishes ``event_payload`` to all registered subscribers."""


# ---------------------------------------------------------------------------
# Default in-process implementation
# ---------------------------------------------------------------------------

class InMemoryEventBus(AbstractEventBus):
    """
    Resilient in-process event bus backed by Python asyncio.

    Designed for single-process deployments (development, small-scale production).
    Replace with a ``RedisEventBus`` or ``RabbitMQEventBus`` implementation when
    horizontal scaling or guaranteed delivery is required — callers remain unchanged.

    Handler failures are isolated: one failing handler never blocks others.
    All events (including their final dispatch status) are persisted to EventStore
    in a single DB session *after* all handlers have run.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[BaseEventPayload], Awaitable[None]]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[BaseEventPayload], Awaitable[None]]):
        """Registers a handler for the given event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Handler %s subscribed to %s", handler.__name__, event_type)

    async def emit(self, event_payload: BaseEventPayload):
        """
        Publishes an event, runs all registered handlers concurrently, then persists
        the outcome to EventStore in a single DB write.

        The correlation ID is auto-populated from the active request context when not
        already set, enabling cross-module traceability without manual propagation.
        """
        # Auto-inject correlation ID from the active request context when not provided.
        if not event_payload.correlation_id:
            try:
                from .middleware import correlation_id_context
                event_payload.correlation_id = correlation_id_context.get()
            except Exception:
                pass

        # Trigger notification dispatch asynchronously (fire-and-forget, non-blocking).
        try:
            from .notifications import NotificationService
            asyncio.create_task(NotificationService.process_event_notifications(event_payload))
        except Exception as exc:
            logger.error(
                "Failed to schedule NotificationService for event %s: %s",
                event_payload.event_type, exc,
            )

        handlers = self._subscribers.get(event_payload.event_type, [])
        if not handlers:
            logger.debug("No handlers registered for event: %s", event_payload.event_type)

        handler_count = len(handlers)
        completed = 0
        errors: list[str] = []

        async def _safe_execute(handler: Callable, payload: BaseEventPayload):
            nonlocal completed
            try:
                await handler(payload)
                completed += 1
            except Exception as exc:
                errors.append(str(exc))
                logger.error(
                    "Event handler %s failed for %s: %s",
                    handler.__name__, payload.event_type, exc,
                    exc_info=True,
                )

        if handlers:
            await asyncio.gather(*(_safe_execute(h, event_payload) for h in handlers))

        # Persist final event status in a single DB commit after all handlers complete.
        await self._persist_event(event_payload, handler_count, completed, errors)

    async def _persist_event(
        self,
        payload: BaseEventPayload,
        handler_count: int,
        completed: int,
        errors: list[str],
    ):
        """
        Writes the event and its final dispatch outcome to EventStore in one DB session.

        Status values:
        - ``FAILED``    — every handler raised an exception.
        - ``PARTIAL``   — some handlers succeeded, some failed.
        - ``PROCESSED`` — all handlers completed without error.
        - ``EMITTED``   — no subscribers were registered; event is recorded but unhandled.
        """
        try:
            from .audit import EventStore
            from .database import get_session_maker

            if errors and completed == 0:
                final_status = "FAILED"
            elif errors:
                final_status = "PARTIAL"
            elif handler_count > 0:
                final_status = "PROCESSED"
            else:
                final_status = "EMITTED"

            session_maker = get_session_maker()
            async with session_maker() as session:
                event_record = EventStore(
                    id=payload.event_id,
                    event_type=payload.event_type,
                    emitter_module=payload.emitter_module,
                    correlation_id=payload.correlation_id,
                    payload=payload.data,
                    status=final_status,
                    handler_count=handler_count,
                    handlers_completed=completed,
                    processed_at=datetime.now(timezone.utc),
                    error_message="; ".join(errors) if errors else None,
                )
                session.add(event_record)
                await session.commit()
        except Exception as exc:
            logger.warning("Could not persist event %s to EventStore: %s", payload.event_type, exc)


# ---------------------------------------------------------------------------
# Singleton — import this throughout the codebase
# ---------------------------------------------------------------------------

event_bus: AbstractEventBus = InMemoryEventBus()
