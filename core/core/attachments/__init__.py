"""Attachments — File attachment service for any entity."""
from .models import EntityAttachment
from .service import AttachmentService

__all__ = ["EntityAttachment", "AttachmentService"]
