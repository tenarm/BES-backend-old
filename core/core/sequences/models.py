"""Number Sequences — Database models."""
from datetime import datetime
from typing import Optional

from sqlmodel import Field

from ..models.base import BESBase


class NumberSequence(BESBase, table=True):
    """
    Configurable number sequence for generating gap-free reference numbers.

    Each entity type (quotation, sales_order, invoice, etc.) has its own
    sequence with a configurable prefix, pattern, and reset frequency.

    Pattern variables:
    - {PREFIX}: The sequence prefix (e.g., 'QUO', 'SO', 'INV')
    - {YYYY}: Current year (4 digits)
    - {YY}: Current year (2 digits)
    - {MM}: Current month (2 digits)
    - {SEQ:05d}: Sequence number, zero-padded to 5 digits

    Example patterns:
    - '{PREFIX}-{YYYY}{SEQ:05d}' → 'SO-202600001'
    - '{PREFIX}/{YY}-{MM}/{SEQ:04d}' → 'INV/26-05/0001'
    """
    __tablename__ = "number_sequences"

    entity_type: str = Field(index=True, unique=True)  # e.g., 'quotation', 'sales_order'
    prefix: str  # e.g., 'QUO', 'SO', 'INV'
    pattern: str = Field(default="{PREFIX}-{YYYY}{SEQ:05d}")
    current_value: int = Field(default=0)
    reset_frequency: str = Field(default="yearly")  # yearly | monthly | never
    last_reset_at: Optional[datetime] = None
