from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Any
from fastapi import APIRouter


class ExtensionManifest(ABC):
    """
    Formal contract for BES extension modules.
    
    Every extension MUST implement this manifest to be discoverable
    by the dynamic bootstrapper. This replaces the implicit convention
    of expecting a `router.py` with a `router` attribute.
    
    Usage:
        class FinanceManifest(ExtensionManifest):
            @property
            def module_name(self) -> str:
                return "finance"
            
            def get_router(self) -> APIRouter:
                from .router import router
                return router
            
            def get_models(self) -> list[type]:
                from .models import Account, Invoice, JournalEntry, JournalEntryLine
                return [Account, Invoice, JournalEntry, JournalEntryLine]
            
            def get_event_handlers(self) -> dict:
                from .events import register_handlers
                return register_handlers
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """The unique module identifier (e.g., 'finance', 'sales')."""
        ...

    @abstractmethod
    def get_router(self) -> APIRouter:
        """Returns the FastAPI router with all module endpoints."""
        ...

    @abstractmethod
    def get_models(self) -> list[type]:
        """Returns all SQLModel table classes for schema creation."""
        ...

    def get_event_handlers(self) -> dict[str, Callable[..., Awaitable[None]]] | None:
        """
        Returns a dict of {event_type: handler_function} to register
        with the event bus, or None if this module has no subscribers.
        """
        return None

    def on_startup(self) -> None:
        """Optional hook called during application startup."""
        pass

    def on_shutdown(self) -> None:
        """Optional hook called during application shutdown."""
        pass
