"""
Flow Engine — Pydantic schemas for API validation and flow definitions.
"""
import uuid
from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel, Field


class FlowStepCondition(BaseModel):
    """A single condition for decision steps."""
    field: str
    operator: str  # ==, !=, >, <, >=, <=, in, not_in, is_empty, is_not_empty
    value: Any


class FlowStepSideEffect(BaseModel):
    """A side effect triggered when a step completes."""
    type: str  # automation | notification
    action: Optional[str] = None
    target: Optional[str] = None
    template: Optional[str] = None


class FlowStepOwner(BaseModel):
    """Defines who is responsible for a step."""
    type: str  # role | user | initiator | dynamic
    target: str


class FlowStep(BaseModel):
    """A single step in a flow pipeline."""
    id: str
    label: str
    type: str  # action | approval | automation | notification | decision
    description: Optional[str] = None
    status_event: Optional[str] = Field(None, alias="statusEvent")
    entity: Optional[str] = None
    owned_by: Optional[FlowStepOwner] = Field(None, alias="ownedBy")
    required_fields: List[str] = Field(default_factory=list, alias="requiredFields")
    validations: List[dict[str, Any]] = Field(default_factory=list)
    side_effects: List[FlowStepSideEffect] = Field(default_factory=list, alias="sideEffects")
    permissions: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list, alias="dependsOn")
    skippable: bool = False
    conditions: Optional[List[dict[str, Any]]] = None  # For decision steps
    approval_rules: Optional[List[dict[str, Any]]] = Field(None, alias="approvalRules")

    class Config:
        populate_by_name = True


class FlowDefinition(BaseModel):
    """Machine-readable flow definition loaded from flow-definition.json."""
    flow_id: str = Field(alias="flowId")
    display_name: str = Field(alias="displayName")
    description: str
    icon: str
    tier: str  # basic | pro | premium
    primary_module: str = Field(alias="primaryModule")
    supporting_modules: List[str] = Field(default_factory=list, alias="supportingModules")
    default_pipeline: List[FlowStep] = Field(alias="defaultPipeline")
    data_hub_entities: List[str] = Field(default_factory=list, alias="dataHubEntities")
    landing_metrics: List[dict[str, Any]] = Field(default_factory=list, alias="landingMetrics")

    class Config:
        populate_by_name = True


class FlowTaskCreate(BaseModel):
    """Schema for creating a new flow task."""
    flow_id: str
    flow_instance_id: uuid.UUID
    step_id: str
    entity_type: str
    entity_id: uuid.UUID
    assigned_to_role: Optional[str] = None
    assigned_to_user: Optional[uuid.UUID] = None
    priority: str = "normal"
    due_date: Optional[datetime] = None


class FlowTaskRead(BaseModel):
    """Schema for reading a flow task."""
    id: uuid.UUID
    flow_id: str
    flow_instance_id: uuid.UUID
    step_id: str
    entity_type: str
    entity_id: uuid.UUID
    assigned_to_role: Optional[str] = None
    assigned_to_user: Optional[uuid.UUID] = None
    status: str
    priority: str
    due_date: Optional[datetime] = None
    completed_by: Optional[uuid.UUID] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
