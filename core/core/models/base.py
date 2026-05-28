import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON, event
from sqlalchemy.orm import declared_attr


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class BESBase(SQLModel):
    """
    Unified base model for all BES tables.
    Provides UUID primary keys, audit trail, multi-org scoping,
    soft-deletion, and a JSONB expansion joint.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: Optional[str] = Field(default=None)
    subsidiary_id: Optional[str] = Field(default=None, index=True)
    is_deleted: bool = Field(default=False)
    # Using JSON for sqlite compatibility
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)

    # Concurrency control: Optimistic locking version field
    version_id: int = Field(
        default=1,
        sa_column_kwargs={"server_default": "1"}
    )

    @declared_attr
    def __mapper_args__(cls):
        return {
            "version_id_col": cls.version_id
        }



# --- SQLAlchemy event to auto-update `updated_at` on modification ---
@event.listens_for(BESBase, "before_update", propagate=True)
def receive_before_update(mapper, connection, target):
    """Automatically set updated_at to current UTC time before any update."""
    target.updated_at = utc_now()
