from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ResolutionOutcome,
)

class ComplaintAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assigned_to: uuid.UUID
    assigned_at: datetime
    created_at: datetime
    created_by: uuid.UUID | None

class ComplaintResolutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outcome: ResolutionOutcome
    resolution_notes: str
    resolved_by: uuid.UUID
    resolved_at: datetime
    created_at: datetime

class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    order_id: uuid.UUID | None = None
    category: ComplaintCategory
    priority: ComplaintPriority
    status: ComplaintStatus
    description: str
    sla_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    assignments: list[ComplaintAssignmentResponse] = Field(default_factory=list)
    resolution: ComplaintResolutionResponse | None = None

class ComplaintListResponse(BaseModel):
    items: list[ComplaintResponse]
    total: int
    skip: int
    limit: int

class RaiseComplaintRequest(BaseModel):
    customer_id: uuid.UUID
    category: ComplaintCategory
    priority: ComplaintPriority
    description: str = Field(..., min_length=1, max_length=2000)
    order_id: uuid.UUID | None = None

class AssignComplaintRequest(BaseModel):
    assigned_to: uuid.UUID

class ResolveComplaintRequest(BaseModel):
    outcome: ResolutionOutcome
    resolution_notes: str = Field(..., min_length=1, max_length=2000)
