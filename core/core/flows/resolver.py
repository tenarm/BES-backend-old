"""
Flow Engine — Pipeline resolver.

Loads default flow definitions from JSON files and merges
tenant-specific pipeline overrides from the database.

Resolution order:
1. Load default pipeline from flow-definition.json
2. Apply tenant override: insert custom steps, remove skipped steps, reorder
3. Evaluate decision step conditions against current entity data
4. Resolve approval routing based on approval rules
"""
import json
import logging
from pathlib import Path
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import FlowPipelineOverride
from .schemas import FlowDefinition, FlowStep
from ..database import subsidiary_id_context

logger = logging.getLogger(__name__)


class FlowResolver:
    """
    Resolves the effective pipeline for a given flow,
    merging the default definition with tenant customizations.
    """

    def __init__(self, definitions_dir: str | Path):
        """
        Args:
            definitions_dir: Path to the directory containing flow-definition.json files.
                             Expected structure: <dir>/<flow_id>/flow-definition.json
        """
        self._definitions_dir = Path(definitions_dir)
        self._cache: dict[str, FlowDefinition] = {}

    def load_definitions(self) -> dict[str, FlowDefinition]:
        """
        Scans the definitions directory and loads all flow-definition.json files.
        Results are cached for subsequent calls.
        """
        if self._cache:
            return self._cache

        if not self._definitions_dir.exists():
            logger.warning(f"Flow definitions directory not found: {self._definitions_dir}")
            return {}

        for flow_dir in self._definitions_dir.iterdir():
            if not flow_dir.is_dir():
                continue

            definition_file = flow_dir / "flow-definition.json"
            if not definition_file.exists():
                continue

            try:
                with open(definition_file, "r") as f:
                    data = json.load(f)
                flow_def = FlowDefinition.model_validate(data)
                self._cache[flow_def.flow_id] = flow_def
                logger.info(f"Loaded flow definition: {flow_def.flow_id} ({flow_def.display_name})")
            except Exception as e:
                logger.error(f"Failed to load flow definition from {definition_file}: {e}")

        return self._cache

    def get_definition(self, flow_id: str) -> Optional[FlowDefinition]:
        """Get a specific flow definition by ID."""
        definitions = self.load_definitions()
        return definitions.get(flow_id)

    async def resolve_pipeline(
        self,
        session: AsyncSession,
        flow_id: str,
    ) -> list[FlowStep]:
        """
        Resolves the effective pipeline for a flow, applying tenant overrides.

        Returns the ordered list of FlowStep objects after merging:
        1. Default pipeline from flow-definition.json
        2. Custom steps added by the tenant
        3. Skipped steps removed
        4. Custom step ordering applied
        """
        flow_def = self.get_definition(flow_id)
        if not flow_def:
            logger.warning(f"No flow definition found for flow_id: {flow_id}")
            return []

        # Start with the default pipeline
        steps_by_id: dict[str, FlowStep] = {
            step.id: step for step in flow_def.default_pipeline
        }

        # Load tenant overrides
        subsidiary_id = subsidiary_id_context.get()
        override = await self._get_override(session, flow_id, subsidiary_id)

        if override:
            # Add custom steps
            for custom_step_data in (override.custom_steps or []):
                try:
                    custom_step = FlowStep.model_validate(custom_step_data)
                    steps_by_id[custom_step.id] = custom_step
                except Exception as e:
                    logger.error(f"Invalid custom step in override for {flow_id}: {e}")

            # Remove skipped steps
            for skipped_id in (override.skipped_steps or []):
                steps_by_id.pop(skipped_id, None)

            # Apply custom ordering if provided
            if override.step_order:
                ordered_steps = []
                for step_id in override.step_order:
                    if step_id in steps_by_id:
                        ordered_steps.append(steps_by_id[step_id])
                # Append any steps not in the custom order (safety net)
                for step_id, step in steps_by_id.items():
                    if step not in ordered_steps:
                        ordered_steps.append(step)
                return ordered_steps

        # Return default order if no custom ordering
        return list(steps_by_id.values())

    async def _get_override(
        self,
        session: AsyncSession,
        flow_id: str,
        subsidiary_id: Optional[str],
    ) -> Optional[FlowPipelineOverride]:
        """Load tenant-specific pipeline override from the database."""
        stmt = select(FlowPipelineOverride).where(
            FlowPipelineOverride.flow_id == flow_id,
            FlowPipelineOverride.is_deleted == False,
        )
        if subsidiary_id:
            stmt = stmt.where(FlowPipelineOverride.subsidiary_id == subsidiary_id)

        result = await session.execute(stmt)
        return result.scalars().first()

    def reload(self) -> None:
        """Clear the cache and reload definitions from disk."""
        self._cache.clear()
        self.load_definitions()
