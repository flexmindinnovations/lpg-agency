"""Pydantic request/response models for `api/v1/routers/onboarding_draft.py`.

`uuid`/`datetime` are real imports, not `TYPE_CHECKING`-guarded — see
`schemas/customer.py`'s identical note on why, with `from __future__ import
annotations` active.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SaveOnboardingDraftRequest(BaseModel):
    draft_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    current_step: int = 1
    registration_data: dict[str, Any] = {}
    address_data: dict[str, Any] = {}
    kyc_data: dict[str, Any] = {}
    kyc_document_blob_ref: str | None = None


class OnboardingDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID | None
    current_step: int
    registration_data: dict[str, Any]
    address_data: dict[str, Any]
    kyc_data: dict[str, Any]
    kyc_document_blob_ref: str | None
    created_at: datetime | None
    updated_at: datetime | None


class OnboardingDraftListResponse(BaseModel):
    items: list[OnboardingDraftResponse]
