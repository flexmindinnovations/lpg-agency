"""ComplianceDocument aggregate root.

A statutory document held against a driver or a vehicle — driving licence,
vehicle RC, insurance, fitness, PUC, PESO transport licence, TREM card,
refresher-training certificate. Modelled as its own aggregate keyed by
``(owner_type, owner_id)`` rather than nested inside ``Driver`` / ``Vehicle``:
both owners handle documents identically, so one aggregate + one repository is
DRYer than duplicating child-entity logic in two places (consistent with the
Branch/Warehouse "independent aggregate" divergence in Phase 7).

Lifecycle of ``verification_status``:  pending → verified
                                       pending → rejected → pending (on replace)

docs/research/feature-gap-analysis.md D24 · planning/features/20-regulatory-compliance
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, date, datetime

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

COMPLIANCE_OWNER_TYPES: frozenset[str] = frozenset({"driver", "vehicle"})

# doc_type → the owner it may be attached to.
_DRIVER_DOC_TYPES: frozenset[str] = frozenset(
    {
        "driving_licence",
        "dl_hazmat_endorsement",
        "trem_card",
        "driver_training_certificate",
    }
)
_VEHICLE_DOC_TYPES: frozenset[str] = frozenset(
    {
        "vehicle_rc",
        "vehicle_insurance",
        "vehicle_fitness",
        "vehicle_puc",
        "peso_transport_licence",
    }
)
COMPLIANCE_DOC_TYPES: frozenset[str] = _DRIVER_DOC_TYPES | _VEHICLE_DOC_TYPES

# The one document each owner must have on file before it can be registered
# (enforced by RegisterDriverUseCase / RegisterVehicleUseCase, not here).
REQUIRED_DOC_TYPE_FOR_OWNER: dict[str, str] = {
    "driver": "driving_licence",
    "vehicle": "vehicle_rc",
}

# Document types that legitimately carry no expiry date (a TREM card is tied
# to the consignment, a training certificate may be issued without one).
_NO_EXPIRY_DOC_TYPES: frozenset[str] = frozenset({"trem_card"})

COMPLIANCE_VERIFICATION_STATUSES: frozenset[str] = frozenset({"pending", "verified", "rejected"})


def doc_types_for_owner(owner_type: str) -> frozenset[str]:
    """The document types valid for a given owner type."""
    return _DRIVER_DOC_TYPES if owner_type == "driver" else _VEHICLE_DOC_TYPES


# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComplianceDocumentAdded(DomainEvent):
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    doc_type: str
    expiry_date: date | None


@dataclass(frozen=True, slots=True)
class ComplianceDocumentReplaced(DomainEvent):
    document_id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    doc_type: str
    expiry_date: date | None


@dataclass(frozen=True, slots=True)
class ComplianceDocumentVerified(DomainEvent):
    document_id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    doc_type: str
    status: str  # "verified" | "rejected"


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class ComplianceDocument(AggregateRoot):
    """Compliance document aggregate root.

    Business invariants:
    - ``owner_type`` ∈ {driver, vehicle}; ``doc_type`` must be valid for it.
    - ``document_number`` non-empty.
    - ``expiry_date`` is required unless ``doc_type`` is in the no-expiry set;
      when both are set, it must be after ``issue_date``.
    - ``verification_status`` transitions follow the documented lifecycle.
    """

    __slots__ = (
        "_doc_type",
        "_document_number",
        "_expiry_date",
        "_file_ref",
        "_issue_date",
        "_owner_id",
        "_owner_type",
        "_rejection_reason",
        "_tenant_id",
        "_verification_status",
        "_verified_at",
        "_verified_by",
    )

    def __init__(
        self,
        *,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_type: str,
        owner_id: uuid.UUID,
        doc_type: str,
        document_number: str,
        file_ref: str,
        issue_date: date | None = None,
        expiry_date: date | None = None,
        verification_status: str = "pending",
        rejection_reason: str | None = None,
        verified_by: uuid.UUID | None = None,
        verified_at: datetime | None = None,
        version: int = 1,
        _record_event: bool = True,
    ) -> None:
        super().__init__(document_id, version=version)

        self._validate_owner(owner_type)
        self._validate_doc_type(owner_type, doc_type)
        self._validate_document_number(document_number)
        self._validate_dates(doc_type, issue_date, expiry_date)
        if verification_status not in COMPLIANCE_VERIFICATION_STATUSES:
            msg = f"Unknown verification status: '{verification_status}'."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._owner_type = owner_type
        self._owner_id = owner_id
        self._doc_type = doc_type
        self._document_number = document_number
        self._file_ref = file_ref
        self._issue_date = issue_date
        self._expiry_date = expiry_date
        self._verification_status = verification_status
        self._rejection_reason = rejection_reason
        self._verified_by = verified_by
        self._verified_at = verified_at

        if _record_event:
            self.record_event(
                ComplianceDocumentAdded(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    doc_type=doc_type,
                    expiry_date=expiry_date,
                )
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def owner_type(self) -> str:
        return self._owner_type

    @property
    def owner_id(self) -> uuid.UUID:
        return self._owner_id

    @property
    def doc_type(self) -> str:
        return self._doc_type

    @property
    def document_number(self) -> str:
        return self._document_number

    @property
    def file_ref(self) -> str:
        return self._file_ref

    @property
    def issue_date(self) -> date | None:
        return self._issue_date

    @property
    def expiry_date(self) -> date | None:
        return self._expiry_date

    @property
    def verification_status(self) -> str:
        return self._verification_status

    @property
    def rejection_reason(self) -> str | None:
        return self._rejection_reason

    @property
    def verified_by(self) -> uuid.UUID | None:
        return self._verified_by

    @property
    def verified_at(self) -> datetime | None:
        return self._verified_at

    def is_expired(self, *, as_of: date | None = None) -> bool:
        reference = as_of or datetime.now(UTC).date()
        return self._expiry_date is not None and self._expiry_date < reference

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def replace(
        self,
        *,
        document_number: str,
        file_ref: str,
        issue_date: date | None,
        expiry_date: date | None,
    ) -> None:
        """A renewed document supersedes the old one — same slot, new details,
        verification resets to pending."""
        self._validate_document_number(document_number)
        self._validate_dates(self._doc_type, issue_date, expiry_date)

        self._document_number = document_number
        self._file_ref = file_ref
        self._issue_date = issue_date
        self._expiry_date = expiry_date
        self._verification_status = "pending"
        self._rejection_reason = None
        self._verified_by = None
        self._verified_at = None

        self.record_event(
            ComplianceDocumentReplaced(
                document_id=self.id,
                owner_type=self._owner_type,
                owner_id=self._owner_id,
                doc_type=self._doc_type,
                expiry_date=expiry_date,
            )
        )

    def verify(
        self,
        *,
        status: str,
        verified_by: uuid.UUID,
        rejection_reason: str | None = None,
    ) -> None:
        """Mark the document verified or rejected after a manual review."""
        if status not in {"verified", "rejected"}:
            msg = f"Verification status must be 'verified' or 'rejected', got '{status}'."
            raise InvariantViolation(msg)
        if status == "rejected" and not (rejection_reason and rejection_reason.strip()):
            msg = "A rejection reason is required when rejecting a document."
            raise InvariantViolation(msg)

        self._verification_status = status
        self._rejection_reason = rejection_reason if status == "rejected" else None
        self._verified_by = verified_by
        self._verified_at = datetime.now(UTC)

        self.record_event(
            ComplianceDocumentVerified(
                document_id=self.id,
                owner_type=self._owner_type,
                owner_id=self._owner_id,
                doc_type=self._doc_type,
                status=status,
            )
        )

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_owner(owner_type: str) -> None:
        if owner_type not in COMPLIANCE_OWNER_TYPES:
            msg = (
                f"Compliance document owner type '{owner_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(COMPLIANCE_OWNER_TYPES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_doc_type(owner_type: str, doc_type: str) -> None:
        allowed = doc_types_for_owner(owner_type)
        if doc_type not in allowed:
            msg = (
                f"Document type '{doc_type}' is not valid for a {owner_type}. "
                f"Must be one of: {', '.join(sorted(allowed))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_document_number(number: str) -> None:
        if not number or not number.strip():
            msg = "Compliance document number must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_dates(doc_type: str, issue_date: date | None, expiry_date: date | None) -> None:
        if expiry_date is None and doc_type not in _NO_EXPIRY_DOC_TYPES:
            msg = f"An expiry date is required for a '{doc_type}' document."
            raise InvariantViolation(msg)
        if issue_date is not None and expiry_date is not None and expiry_date <= issue_date:
            msg = (
                f"Expiry date {expiry_date.isoformat()} must be after the issue "
                f"date {issue_date.isoformat()}."
            )
            raise InvariantViolation(msg)
