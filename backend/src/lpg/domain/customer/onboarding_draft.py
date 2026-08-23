from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


@dataclass(slots=True)
class OnboardingDraftEntry:
    """A staff user's in-progress Customer Onboarding wizard state.

    Deliberately a thin, no-invariant record rather than a DDD aggregate —
    it is a snapshot of three not-yet-validated form groups (JSON blobs),
    not a business object with its own transitions. Owned by the staff user
    filling it in (`created_by`), never by a customer — the wizard's whole
    point is that no `Customer` aggregate exists yet while a draft does.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: uuid.UUID
    branch_id: uuid.UUID | None
    current_step: int
    registration_data: dict[str, Any] = field(default_factory=dict)
    address_data: dict[str, Any] = field(default_factory=dict)
    kyc_data: dict[str, Any] = field(default_factory=dict)
    kyc_document_blob_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
