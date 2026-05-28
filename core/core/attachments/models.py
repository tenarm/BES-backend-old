"""Attachments — Database models."""
import uuid
from typing import Optional

from sqlmodel import Field

from ..models.base import BESBase


class EntityAttachment(BESBase, table=True):
    """
    A file attachment linked to any entity in the system.

    Attachments are scoped by entity_type + entity_id, and optionally
    by step_id when attached during a specific flow step.

    Categories: document, receipt, photo, contract, other
    """
    __tablename__ = "entity_attachments"

    entity_type: str = Field(index=True)
    entity_id: uuid.UUID = Field(index=True)
    step_id: Optional[str] = None  # Flow step where the file was uploaded
    file_name: str
    file_type: str  # MIME type: application/pdf, image/png, etc.
    file_size: int  # Bytes
    storage_path: str  # Relative path within storage root
    uploaded_by: uuid.UUID
    category: str = Field(default="document")  # document | receipt | photo | contract | other
