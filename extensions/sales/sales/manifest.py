"""Sales extension manifest — formal contract for the bootstrapper."""
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
        from .models import SalesCustomerDetails, Quotation, QuotationItem, SalesOrder
        return [SalesCustomerDetails, Quotation, QuotationItem, SalesOrder]

    def get_event_handlers(self):
        # Sales emits events but doesn't subscribe to any
        return None


manifest = SalesManifest()
