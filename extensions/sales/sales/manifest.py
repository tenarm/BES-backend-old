from fastapi import APIRouter
from core.extension import ExtensionManifest

class SalesManifest(ExtensionManifest):
    @property
    def module_name(self) -> str:
        return "sales"

    def get_router(self) -> APIRouter:
        from .router import router
        return router

    def get_models(self) -> list[type]:
        from .models import SalesEntity, CustomerAddress, CustomerContact, CustomerCredit
        return [SalesEntity, CustomerAddress, CustomerContact, CustomerCredit]

    def get_event_handlers(self):
        from .events import register_event_handlers
        return register_event_handlers

manifest = SalesManifest()
