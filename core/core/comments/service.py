"""
Comments — Service layer.

Handles comment creation, retrieval, editing, and @mention event emission.
Comments are append-only (edits create versioned history).
"""
import uuid
import re
import logging
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import EntityComment

logger = logging.getLogger(__name__)

# Regex to extract @mentions from comment content
MENTION_PATTERN = re.compile(r"@([a-f0-9\-]{36})")


class CommentService:
    """Service for managing entity comments."""

    async def create(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
        author_id: uuid.UUID,
        content: str,
        is_internal: bool = True,
        step_id: Optional[str] = None,
    ) -> EntityComment:
        """
        Create a new comment on an entity.

        Automatically extracts @mentions from the content and stores them.
        After commit, the caller should emit COMMENT_MENTION events for each mention.
        """
        # Extract @mentions
        mentions = MENTION_PATTERN.findall(content)

        comment = EntityComment(
            entity_type=entity_type,
            entity_id=entity_id,
            step_id=step_id,
            author_id=author_id,
            content=content,
            is_internal=is_internal,
            mentions=mentions,
        )
        session.add(comment)
        await session.flush()
        await session.refresh(comment)

        logger.info(f"Comment created on {entity_type}/{entity_id} by {author_id}")
        return comment

    async def get_for_entity(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Sequence[EntityComment]:
        """Get all comments for an entity, ordered by creation time."""
        stmt = (
            select(EntityComment)
            .where(EntityComment.entity_type == entity_type)
            .where(EntityComment.entity_id == entity_id)
            .order_by(EntityComment.created_at.asc())
        )
        if not include_deleted:
            stmt = stmt.where(EntityComment.is_deleted == False)

        result = await session.execute(stmt)
        return result.scalars().all()

    async def update(
        self,
        session: AsyncSession,
        comment_id: uuid.UUID,
        content: str,
    ) -> Optional[EntityComment]:
        """
        Update a comment's content.

        Re-extracts @mentions from the new content.
        """
        stmt = select(EntityComment).where(EntityComment.id == comment_id)
        result = await session.execute(stmt)
        comment = result.scalars().first()

        if comment and not comment.is_deleted:
            comment.content = content
            comment.mentions = MENTION_PATTERN.findall(content)
            session.add(comment)
            await session.flush()
            await session.refresh(comment)
            logger.info(f"Comment {comment_id} updated")

        return comment
