"""Comments — Database models."""
import uuid
from typing import Optional, Any, List

from sqlmodel import Field
from sqlalchemy import Column, JSON

from ..models.base import BESBase


class EntityComment(BESBase, table=True):
    """
    A comment attached to any entity in the system.

    Comments are append-only — edits create versioned history.
    Physical deletion is forbidden; use is_deleted for removal.

    is_internal: True = visible only to internal staff, False = visible to external parties too.
    """
    __tablename__ = "entity_comments"

    entity_type: str = Field(index=True)
    entity_id: uuid.UUID = Field(index=True)
    step_id: Optional[str] = None  # Flow step context
    author_id: uuid.UUID
    content: str
    is_internal: bool = Field(default=True)
    mentions: List[str] = Field(default_factory=list, sa_column=Column(JSON))  # List of user IDs mentioned
