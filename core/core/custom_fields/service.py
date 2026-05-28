"""
Custom Fields — Service layer.

Manages custom field definitions and validates entity metadata_ against them.
"""
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import CustomFieldDefinition
from ..database import subsidiary_id_context

logger = logging.getLogger(__name__)

# Valid field types
VALID_FIELD_TYPES = {
    "text", "number", "decimal", "date",
    "select", "multiselect", "boolean",
    "url", "email",
}


class CustomFieldService:
    """Service for managing tenant-defined custom fields."""

    async def get_definitions(
        self,
        session: AsyncSession,
        entity_type: str,
    ) -> Sequence[CustomFieldDefinition]:
        """Get all custom field definitions for an entity type."""
        stmt = (
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.entity_type == entity_type)
            .where(CustomFieldDefinition.is_deleted == False)
            .order_by(CustomFieldDefinition.display_order)
        )
        # Apply subsidiary scoping
        subsidiary_id = subsidiary_id_context.get()
        if subsidiary_id:
            stmt = stmt.where(CustomFieldDefinition.subsidiary_id == subsidiary_id)

        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_definition(
        self,
        session: AsyncSession,
        entity_type: str,
        field_key: str,
        field_label: str,
        field_type: str,
        **kwargs: Any,
    ) -> CustomFieldDefinition:
        """Create a new custom field definition."""
        from ..exceptions import ValidationError

        if field_type not in VALID_FIELD_TYPES:
            raise ValidationError(
                f"Invalid field_type: {field_type}. Must be one of: {', '.join(VALID_FIELD_TYPES)}",
                field="field_type",
            )

        definition = CustomFieldDefinition(
            entity_type=entity_type,
            field_key=field_key,
            field_label=field_label,
            field_type=field_type,
            **kwargs,
        )
        session.add(definition)
        await session.flush()
        await session.refresh(definition)

        logger.info(f"Created custom field '{field_key}' for {entity_type}")
        return definition

    def validate_metadata(
        self,
        definitions: Sequence[CustomFieldDefinition],
        metadata: dict[str, Any],
    ) -> list[str]:
        """
        Validate entity metadata_ against custom field definitions.

        Returns a list of validation error messages (empty if valid).
        """
        errors: list[str] = []

        for defn in definitions:
            value = metadata.get(defn.field_key)

            # Check required fields
            if defn.is_required and (value is None or value == ""):
                errors.append(f"Custom field '{defn.field_label}' is required")
                continue

            if value is None:
                continue

            # Type-specific validation
            if defn.field_type == "number":
                try:
                    int(value)
                except (ValueError, TypeError):
                    errors.append(f"'{defn.field_label}' must be a whole number")

            elif defn.field_type == "decimal":
                try:
                    float(value)
                except (ValueError, TypeError):
                    errors.append(f"'{defn.field_label}' must be a number")

            elif defn.field_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(f"'{defn.field_label}' must be true or false")

            elif defn.field_type == "select":
                valid_values = [opt.get("value") for opt in (defn.options or [])]
                if value not in valid_values:
                    errors.append(f"'{defn.field_label}' must be one of: {', '.join(str(v) for v in valid_values)}")

            elif defn.field_type == "multiselect":
                if not isinstance(value, list):
                    errors.append(f"'{defn.field_label}' must be a list")
                else:
                    valid_values = [opt.get("value") for opt in (defn.options or [])]
                    for v in value:
                        if v not in valid_values:
                            errors.append(f"'{defn.field_label}' contains invalid value: {v}")

        return errors
