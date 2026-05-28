"""
Flow Engine — Database models.

These models support multi-role flow orchestration, pipeline customization,
and cross-flow entity linking.
"""
import uuid
from datetime import datetime
from typing import Optional, Any, List

from sqlmodel import Field
from sqlalchemy import Column, JSON

from ..models.base import BESBase


class FlowPipelineOverride(BESBase, table=True):
    """
    Per-tenant pipeline customization for a flow.

    Stores the delta on top of the default pipeline from flow-definition.json:
    - custom_steps: Steps added by the tenant (approval gates, automations, etc.)
    - skipped_steps: Step IDs the tenant has disabled
    - step_order: Full ordered list of step IDs (including custom ones)
    """
    __tablename__ = "flow_pipeline_overrides"

    flow_id: str = Field(index=True)
    custom_steps: List[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    skipped_steps: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    step_order: List[str] = Field(default_factory=list, sa_column=Column(JSON))


class FlowTask(BESBase, table=True):
    """
    A pending task within a flow, assigned to a role or specific user.

    When a flow step completes and the next step has a different owner,
    a FlowTask is created to notify the new owner. This powers the
    "My Tasks" inbox across all flows.
    """
    __tablename__ = "flow_tasks"

    flow_id: str = Field(index=True)
    flow_instance_id: uuid.UUID = Field(index=True)
    step_id: str
    entity_type: str
    entity_id: uuid.UUID = Field(index=True)
    assigned_to_role: Optional[str] = Field(default=None, index=True)
    assigned_to_user: Optional[uuid.UUID] = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)  # pending | in_progress | completed | skipped
    priority: str = Field(default="normal")  # normal | high | urgent
    due_date: Optional[datetime] = None
    completed_by: Optional[uuid.UUID] = None
    completed_at: Optional[datetime] = None


class FlowEntityLink(BESBase, table=True):
    """
    Links entities across different flows.

    Examples:
    - A SalesOrder in the Sell flow linked to a PurchaseOrder in the Buy flow
    - An Invoice linked to a Payment
    - A Quote converted to a SalesOrder

    link_type values: 'converted_from', 'triggers', 'fulfills', 'pays', 'reverses'
    """
    __tablename__ = "flow_entity_links"

    source_flow: str
    source_entity_type: str
    source_entity_id: uuid.UUID = Field(index=True)
    target_flow: str
    target_entity_type: str
    target_entity_id: uuid.UUID = Field(index=True)
    link_type: str  # converted_from | triggers | fulfills | pays | reverses
