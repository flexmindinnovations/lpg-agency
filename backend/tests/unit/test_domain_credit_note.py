"""Unit tests for the CreditNote aggregate root.

Covers the request/approve two-step workflow and the `RefundApproved`
event (R10) — fired only on approval, never on request.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from lpg.domain.accounting.credit_note import CreditNote, RefundApproved
from lpg.domain.common.base import InvariantViolation


def _request(**kwargs: object) -> CreditNote:
    defaults: dict[str, object] = {
        "credit_note_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "invoice_id": uuid.uuid4(),
        "amount": Decimal("100.00"),
        "reason": "Damaged cylinder returned.",
        "requested_by": uuid.uuid4(),
        "credit_note_number": "CRN000001",
    }
    defaults.update(kwargs)
    return CreditNote.request(**defaults)  # type: ignore[arg-type]


class TestCreditNoteRequest:
    def test_starts_unapproved(self) -> None:
        credit_note = _request()
        assert credit_note.is_approved is False
        assert credit_note.approved_by is None
        assert credit_note.approved_at is None

    def test_records_no_event(self) -> None:
        """`RefundApproved` only fires on approval, matching the name."""
        credit_note = _request()
        assert credit_note.events == ()

    def test_rejects_zero_amount(self) -> None:
        with pytest.raises(InvariantViolation, match="must be > 0"):
            _request(amount=Decimal("0"))

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(InvariantViolation, match="must be > 0"):
            _request(amount=Decimal("-1"))

    def test_rejects_empty_reason(self) -> None:
        with pytest.raises(InvariantViolation, match="reason must not be empty"):
            _request(reason="   ")


class TestApprove:
    def test_approve_sets_approved_fields(self) -> None:
        credit_note = _request()
        approved_by = uuid.uuid4()

        credit_note.approve(approved_by)

        assert credit_note.is_approved is True
        assert credit_note.approved_by == approved_by
        assert credit_note.approved_at is not None

    def test_approve_records_refund_approved_event(self) -> None:
        credit_note = _request(amount=Decimal("250.00"))
        approved_by = uuid.uuid4()

        credit_note.approve(approved_by)

        events = [e for e in credit_note.events if isinstance(e, RefundApproved)]
        assert len(events) == 1
        event = events[0]
        assert event.credit_note_id == credit_note.id
        assert event.tenant_id == credit_note.tenant_id
        assert event.invoice_id == credit_note.invoice_id
        assert event.amount == Decimal("250.00")
        assert event.approved_by == approved_by

    def test_approve_twice_raises(self) -> None:
        credit_note = _request()
        credit_note.approve(uuid.uuid4())

        with pytest.raises(InvariantViolation, match="already been approved"):
            credit_note.approve(uuid.uuid4())
