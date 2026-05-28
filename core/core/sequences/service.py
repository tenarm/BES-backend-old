"""
Number Sequences — Service layer.

Generates gap-free reference numbers using pessimistic locking (FOR UPDATE).
Numbers are never reused or recycled, even for cancelled entities.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import NumberSequence

logger = logging.getLogger(__name__)


class SequenceService:
    """
    Service for generating sequential, gap-free reference numbers.

    Usage from extension services:
        sequence_service = SequenceService()
        ref_number = await sequence_service.next_number(session, "sales_order")
        # Returns: 'SO-202600042'
    """

    async def next_number(self, session: AsyncSession, entity_type: str) -> str:
        """
        Generate the next number in the sequence for a given entity type.

        Uses SELECT FOR UPDATE to prevent duplicate numbers under
        concurrent requests. The caller MUST commit the session after
        this call to release the lock.

        Args:
            session: Active async database session (shared transaction).
            entity_type: The entity type key (e.g., 'sales_order', 'invoice').

        Returns:
            Formatted reference number string.

        Raises:
            EntityNotFoundError: If no sequence is configured for the entity type.
        """
        # Lock the sequence row for update
        stmt = (
            select(NumberSequence)
            .where(NumberSequence.entity_type == entity_type)
            .where(NumberSequence.is_deleted == False)
            .with_for_update()
        )
        result = await session.execute(stmt)
        sequence = result.scalars().first()

        if not sequence:
            from ..exceptions import EntityNotFoundError
            raise EntityNotFoundError("NumberSequence", entity_type)

        # Check if reset is needed
        now = datetime.now(timezone.utc)
        if self._should_reset(sequence, now):
            sequence.current_value = 0
            sequence.last_reset_at = now

        # Increment
        sequence.current_value += 1

        # Format the number
        formatted = self._format_number(sequence, now)

        session.add(sequence)
        await session.flush()

        logger.info(f"Generated sequence {formatted} for {entity_type}")
        return formatted

    def _should_reset(self, sequence: NumberSequence, now: datetime) -> bool:
        """Check if the sequence counter should reset based on frequency."""
        if sequence.reset_frequency == "never":
            return False

        if sequence.last_reset_at is None:
            return False  # First use, don't reset

        last = sequence.last_reset_at

        if sequence.reset_frequency == "yearly":
            return now.year > last.year

        if sequence.reset_frequency == "monthly":
            return (now.year, now.month) > (last.year, last.month)

        return False

    def _format_number(self, sequence: NumberSequence, now: datetime) -> str:
        """Format the reference number using the configured pattern."""
        pattern = sequence.pattern

        # Replace pattern variables
        result = pattern.replace("{PREFIX}", sequence.prefix)
        result = result.replace("{YYYY}", str(now.year))
        result = result.replace("{YY}", str(now.year)[-2:])
        result = result.replace("{MM}", str(now.month).zfill(2))

        # Handle {SEQ:XXd} pattern (e.g., {SEQ:05d} → 00042)
        import re
        seq_match = re.search(r"\{SEQ:(\d+)d\}", result)
        if seq_match:
            pad_width = int(seq_match.group(1))
            formatted_seq = str(sequence.current_value).zfill(pad_width)
            result = re.sub(r"\{SEQ:\d+d\}", formatted_seq, result)
        else:
            result = result.replace("{SEQ}", str(sequence.current_value))

        return result

    async def ensure_sequence(
        self,
        session: AsyncSession,
        entity_type: str,
        prefix: str,
        pattern: str = "{PREFIX}-{YYYY}{SEQ:05d}",
        reset_frequency: str = "yearly",
    ) -> NumberSequence:
        """
        Ensure a sequence exists for an entity type, creating it if missing.

        Idempotent — safe to call on every startup.
        """
        stmt = select(NumberSequence).where(NumberSequence.entity_type == entity_type)
        result = await session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            return existing

        sequence = NumberSequence(
            entity_type=entity_type,
            prefix=prefix,
            pattern=pattern,
            reset_frequency=reset_frequency,
        )
        session.add(sequence)
        await session.flush()
        await session.refresh(sequence)

        logger.info(f"Created number sequence for {entity_type}: {prefix}")
        return sequence
