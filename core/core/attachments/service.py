"""
Attachments — Service layer.

Handles file upload, retrieval, and soft-deletion.
Storage backend is pluggable (local filesystem for dev, S3/GCS for production).
"""
import uuid
import logging
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import EntityAttachment
from ..database import subsidiary_id_context

logger = logging.getLogger(__name__)

# Allowed MIME types per Rule §19
ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "text/csv",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class AttachmentService:
    """Service for managing entity file attachments."""

    def __init__(self, storage_root: str = "storage"):
        self.storage_root = Path(storage_root)

    async def upload(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
        file_name: str,
        file_type: str,
        file_size: int,
        file_content: bytes,
        uploaded_by: uuid.UUID,
        category: str = "document",
        step_id: Optional[str] = None,
    ) -> EntityAttachment:
        """
        Upload a file and create an attachment record.

        Validates file type and size before saving.
        """
        if file_type not in ALLOWED_TYPES:
            from ..exceptions import ValidationError
            raise ValidationError(
                f"File type '{file_type}' is not allowed. Allowed types: PDF, PNG, JPG, WEBP, XLSX, CSV",
                field="file_type",
            )

        if file_size > MAX_FILE_SIZE:
            from ..exceptions import ValidationError
            raise ValidationError(
                f"File size ({file_size} bytes) exceeds maximum of {MAX_FILE_SIZE} bytes",
                field="file_size",
            )

        # Build storage path: storage/<tenant_id>/<entity_type>/<entity_id>/
        tenant_id = subsidiary_id_context.get() or "default"
        relative_path = f"{tenant_id}/{entity_type}/{entity_id}/{file_name}"
        full_path = self.storage_root / relative_path

        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        full_path.write_bytes(file_content)

        # Create DB record
        attachment = EntityAttachment(
            entity_type=entity_type,
            entity_id=entity_id,
            step_id=step_id,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            storage_path=relative_path,
            uploaded_by=uploaded_by,
            category=category,
        )
        session.add(attachment)
        await session.flush()
        await session.refresh(attachment)

        logger.info(f"Uploaded attachment {file_name} for {entity_type}/{entity_id}")
        return attachment

    async def get_for_entity(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> Sequence[EntityAttachment]:
        """Get all non-deleted attachments for an entity."""
        stmt = (
            select(EntityAttachment)
            .where(EntityAttachment.entity_type == entity_type)
            .where(EntityAttachment.entity_id == entity_id)
            .where(EntityAttachment.is_deleted == False)
            .order_by(EntityAttachment.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def soft_delete(
        self,
        session: AsyncSession,
        attachment_id: uuid.UUID,
    ) -> Optional[EntityAttachment]:
        """Soft delete an attachment. Does NOT delete the physical file."""
        stmt = select(EntityAttachment).where(EntityAttachment.id == attachment_id)
        result = await session.execute(stmt)
        attachment = result.scalars().first()

        if attachment and not attachment.is_deleted:
            attachment.is_deleted = True
            session.add(attachment)
            await session.flush()
            await session.refresh(attachment)
            logger.info(f"Soft-deleted attachment {attachment_id}")

        return attachment
