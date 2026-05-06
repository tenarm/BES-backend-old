from typing import Callable, Any, Dict, List
import asyncio

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def emit(self, event_type: str, payload: Any):
        if event_type in self._subscribers:
            handlers = self._subscribers[event_type]
            await asyncio.gather(*(handler(payload) for handler in handlers))

event_bus = EventBus()
