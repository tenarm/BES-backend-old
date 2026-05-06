import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Awaitable
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Typed Payloads ---
class BaseEventPayload(BaseModel):
    """
    Standard envelope for all inter-module events.
    Ensures type safety and standard metadata across the system.
    """
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    emitter_module: str
    event_type: str
    data: Dict[str, Any]

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

# --- Resilient In-Memory Implementation ---
class InMemoryEventBus(AbstractEventBus):
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[BaseEventPayload], Awaitable[None]]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[BaseEventPayload], Awaitable[None]]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Handler {handler.__name__} subscribed to {event_type}")

    async def emit(self, event_payload: BaseEventPayload):
        handlers = self._subscribers.get(event_payload.event_type, [])
        if not handlers:
            logger.debug(f"No handlers found for event: {event_payload.event_type}")
            return
            
        async def safe_execute(handler: Callable, payload: BaseEventPayload):
            try:
                # Elevate context if needed, or handlers can manage their own context
                await handler(payload)
            except Exception as e:
                # 🛑 Resilience: One crashed listener shouldn't break the emitter!
                logger.error(f"Event handler {handler.__name__} failed for event {payload.event_type}: {e}", exc_info=True)
                # In Day 2, we would push this to a Dead Letter Queue (DLQ) here.

        # Run all handlers concurrently but safely
        await asyncio.gather(*(safe_execute(handler, event_payload) for handler in handlers))

# Singleton instance
event_bus: AbstractEventBus = InMemoryEventBus()
