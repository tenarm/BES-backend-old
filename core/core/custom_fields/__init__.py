"""Custom Fields — Tenant-defined field extensibility service."""
from .models import CustomFieldDefinition
from .service import CustomFieldService

__all__ = ["CustomFieldDefinition", "CustomFieldService"]
