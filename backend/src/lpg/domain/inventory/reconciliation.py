"""Physical-count reconciliation rules (D-16, maker-checker).

A `ReconciliationRecord` is a two-step record: a counter records what they
physically found, and a *different* person with `reconciliation:approve`
approves or rejects it. Stock only changes on approval
(`InventoryLocation.apply_count_variance`), exactly once.

The record itself is persisted as a plain row (see the module docstring of
`inventory_location.py` for why it is not loaded through the aggregate);
these are the rules every decision on it must pass, kept here so the
application layer cannot skip one.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from lpg.domain.common.base import BusinessRuleViolation, InvariantViolation

RECONCILIATION_STATES: frozenset[str] = frozenset({"pending", "approved", "rejected"})


class ReconciliationAlreadyDecidedError(InvariantViolation):
    """The count was already approved or rejected — a decision is final."""

    error_code = "RECONCILIATION_ALREADY_DECIDED"


class SelfApprovalNotAllowedError(BusinessRuleViolation):
    """The person who counted the stock cannot approve or reject the count."""

    error_code = "SELF_APPROVAL_NOT_ALLOWED"


def reconciliation_state(*, approved_at: datetime | None, rejected_at: datetime | None) -> str:
    if approved_at is not None:
        return "approved"
    if rejected_at is not None:
        return "rejected"
    return "pending"


def ensure_reconciliation_decidable(
    *,
    record_id: uuid.UUID,
    recorded_by: uuid.UUID,
    decided_by: uuid.UUID,
    approved_at: datetime | None,
    rejected_at: datetime | None,
    allow_self_approval: bool = False,
) -> None:
    """Raises unless `decided_by` may approve or reject this pending count."""
    state = reconciliation_state(approved_at=approved_at, rejected_at=rejected_at)
    if state != "pending":
        msg = f"This count was already {state}."
        raise ReconciliationAlreadyDecidedError(msg, record_id=str(record_id), state=state)
    if recorded_by == decided_by and not allow_self_approval:
        msg = "You recorded this count, so someone else has to approve or reject it."
        raise SelfApprovalNotAllowedError(msg, record_id=str(record_id))
