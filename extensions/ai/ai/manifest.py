from fastapi import APIRouter
from core.extension import ExtensionManifest

class AiManifest(ExtensionManifest):
    @property
    def module_name(self) -> str:
        return "ai"

    def get_router(self) -> APIRouter:
        from .router import router
        return router

    def get_models(self) -> list[type]:
        from .models import AiEntity
        return [AiEntity]

    def get_event_handlers(self):
        from .events import register_event_handlers
        return register_event_handlers

manifest = AiManifest()
