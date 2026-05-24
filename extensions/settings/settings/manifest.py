from fastapi import APIRouter
from core.extension import ExtensionManifest

class SettingsManifest(ExtensionManifest):
    @property
    def module_name(self) -> str:
        return "settings"

    def get_router(self) -> APIRouter:
        from .router import router
        return router

    def get_models(self) -> list[type]:
        from .models import (
            SettingsEntity,
            CompanyProfile,
            Subsidiary,
            FiscalYear,
            PostingPeriod,
            TaxProfile,
            SharingRule,
            IntercompanyAccount
        )
        return [
            SettingsEntity,
            CompanyProfile,
            Subsidiary,
            FiscalYear,
            PostingPeriod,
            TaxProfile,
            SharingRule,
            IntercompanyAccount
        ]

    def get_event_handlers(self):
        from .events import register_event_handlers
        return register_event_handlers

manifest = SettingsManifest()
