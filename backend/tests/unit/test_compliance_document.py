"""Unit tests for the ComplianceDocument aggregate."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.compliance_document import (
    COMPLIANCE_OWNER_TYPES,
    ComplianceDocument,
    ComplianceDocumentAdded,
    ComplianceDocumentReplaced,
    ComplianceDocumentVerified,
    doc_types_for_owner,
)


def _doc(**overrides: object) -> ComplianceDocument:
    kwargs: dict[str, object] = {
        "document_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "owner_type": "driver",
        "owner_id": uuid.uuid4(),
        "doc_type": "driving_licence",
        "document_number": "MH1220110012345",
        "file_ref": "tenant/x/compliance-staging/abc_licence.png",
        "expiry_date": date(2030, 1, 1),
    }
    kwargs.update(overrides)
    return ComplianceDocument(**kwargs)  # type: ignore[arg-type]


class TestConstruction:
    def test_records_an_added_event(self) -> None:
        doc = _doc()
        assert isinstance(doc.events[0], ComplianceDocumentAdded)
        assert doc.verification_status == "pending"

    def test_rejects_a_doc_type_that_does_not_belong_to_the_owner(self) -> None:
        with pytest.raises(InvariantViolation, match="not valid for a driver"):
            _doc(doc_type="vehicle_rc")

    def test_rejects_an_empty_document_number(self) -> None:
        with pytest.raises(InvariantViolation, match="must not be empty"):
            _doc(document_number="  ")

    def test_requires_an_expiry_date_for_an_expiring_type(self) -> None:
        with pytest.raises(InvariantViolation, match="expiry date is required"):
            _doc(expiry_date=None)

    def test_allows_no_expiry_for_a_trem_card(self) -> None:
        doc = _doc(doc_type="trem_card", expiry_date=None)
        assert doc.expiry_date is None

    def test_rejects_expiry_on_or_before_issue(self) -> None:
        with pytest.raises(InvariantViolation, match="must be after"):
            _doc(issue_date=date(2025, 1, 1), expiry_date=date(2025, 1, 1))


class TestCommands:
    def test_replace_resets_verification_and_records_an_event(self) -> None:
        doc = _doc()
        doc.verify(status="verified", verified_by=uuid.uuid4())
        doc.clear_events()

        doc.replace(
            document_number="MH1220110099999",
            file_ref="tenant/x/compliance-staging/new_licence.png",
            issue_date=date(2024, 1, 1),
            expiry_date=date(2034, 1, 1),
        )

        assert doc.document_number == "MH1220110099999"
        assert doc.verification_status == "pending"
        assert doc.verified_at is None
        assert isinstance(doc.events[0], ComplianceDocumentReplaced)

    def test_verify_rejected_requires_a_reason(self) -> None:
        doc = _doc()
        with pytest.raises(InvariantViolation, match="rejection reason is required"):
            doc.verify(status="rejected", verified_by=uuid.uuid4())

    def test_verify_records_the_verifier_and_an_event(self) -> None:
        doc = _doc()
        doc.clear_events()
        reviewer = uuid.uuid4()

        doc.verify(status="verified", verified_by=reviewer)

        assert doc.verification_status == "verified"
        assert doc.verified_by == reviewer
        assert doc.verified_at is not None
        assert isinstance(doc.events[0], ComplianceDocumentVerified)


class TestExpiry:
    def test_is_expired_compares_against_a_reference_date(self) -> None:
        doc = _doc(expiry_date=date(2020, 1, 1))
        assert doc.is_expired(as_of=date(2026, 1, 1)) is True
        assert doc.is_expired(as_of=date(2019, 1, 1)) is False


class TestWarehouseAndTenantOwners:
    """Compliance Calendar (ADR-044) — widened owner types."""

    def test_accepts_a_warehouse_owner_with_peso_form_f(self) -> None:
        doc = _doc(
            owner_type="warehouse",
            doc_type="peso_form_f",
            document_number="PESO/FORM-F/2026/0042",
            expiry_date=date(2029, 1, 1),
        )
        assert doc.owner_type == "warehouse"
        assert doc.doc_type == "peso_form_f"

    def test_accepts_a_tenant_owner_with_insurance_policy(self) -> None:
        doc = _doc(
            owner_type="tenant",
            doc_type="insurance_policy",
            document_number="INS-2026-998877",
            expiry_date=date(2027, 6, 1),
        )
        assert doc.owner_type == "tenant"
        assert doc.doc_type == "insurance_policy"

    def test_rejects_a_warehouse_doc_type_for_a_tenant_owner(self) -> None:
        with pytest.raises(InvariantViolation, match="not valid for a tenant"):
            _doc(owner_type="tenant", doc_type="peso_form_f", expiry_date=date(2029, 1, 1))

    def test_rejects_a_driver_doc_type_for_a_warehouse_owner(self) -> None:
        with pytest.raises(InvariantViolation, match="not valid for a warehouse"):
            _doc(owner_type="warehouse", doc_type="driving_licence")

    def test_rejects_an_unknown_owner_type(self) -> None:
        with pytest.raises(InvariantViolation, match="not valid"):
            _doc(owner_type="branch", doc_type="peso_form_f")


class TestDocTypesForOwner:
    def test_all_four_owner_types_are_recognized(self) -> None:
        assert frozenset({"driver", "vehicle", "warehouse", "tenant"}) == COMPLIANCE_OWNER_TYPES

    def test_warehouse_doc_types(self) -> None:
        assert doc_types_for_owner("warehouse") == {"peso_form_f"}

    def test_tenant_doc_types(self) -> None:
        assert doc_types_for_owner("tenant") == {"insurance_policy"}

    def test_driver_and_vehicle_doc_types_are_unchanged(self) -> None:
        assert "driving_licence" in doc_types_for_owner("driver")
        assert "vehicle_rc" in doc_types_for_owner("vehicle")
        assert "peso_form_f" not in doc_types_for_owner("driver")

    def test_unknown_owner_type_returns_empty(self) -> None:
        assert doc_types_for_owner("branch") == frozenset()
