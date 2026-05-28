"""Custom Fields — Database models."""
from typing import Optional, Any, List

from sqlmodel import Field
from sqlalchemy import Column, JSON

from ..models.base import BESBase


class CustomFieldDefinition(BESBase, table=True):
    """
    Defines a tenant-created custom field on an entity type.

    Custom field values are stored in the entity's `metadata_` JSON column
    (inherited from BESBase). This table defines the schema/structure
    of those custom fields for validation and UI rendering.

    field_type values: text, number, decimal, date, select, multiselect, boolean, url, email
    """
    __tablename__ = "custom_field_definitions"

    entity_type: str = Field(index=True)  # e.g., 'sales_order', 'customer'
    field_key: str  # Key in metadata_ dict, e.g., 'priority_level'
    field_label: str  # Display label, e.g., 'Priority Level'
    field_type: str  # text | number | decimal | date | select | multiselect | boolean | url | email
    options: Optional[List[dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
    )  # For select/multiselect: [{"value": "high", "label": "High"}, ...]
    is_required: bool = Field(default=False)
    default_value: Optional[str] = None
    display_order: int = Field(default=0)
    show_in_table: bool = Field(default=False)  # Show as column in DataTable
    show_in_detail: bool = Field(default=True)  # Show in DetailPanel
