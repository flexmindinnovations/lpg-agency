from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

# Regex for E.164 phone format validation (+ followed by 10 to 15 digits)
_E164_PHONE_REGEX = re.compile(r"^\+[1-9]\d{9,14}$")

# The nationally-standardized 17-digit LPG ID (Indane/Bharat Gas/HP Gas
# subsidy/KYC identifier) — distinct from `consumer_number`, which is the
# shorter, locally-assigned-by-the-agency number used for refill booking.
_LPG_SUBSIDY_ID_REGEX = re.compile(r"^\d{17}$")


@dataclass(frozen=True, slots=True)
class CustomerRegistered(DomainEvent):
    customer_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    consumer_number: str
    phone_number: str


@dataclass(frozen=True, slots=True)
class CustomerStatusChanged(DomainEvent):
    customer_id: uuid.UUID
    old_status: str
    new_status: str


@dataclass(frozen=True, slots=True)
class AddressAdded(DomainEvent):
    customer_id: uuid.UUID
    address_id: uuid.UUID
    address_line: str


@dataclass(frozen=True, slots=True)
class PrimaryAddressSet(DomainEvent):
    customer_id: uuid.UUID
    address_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class KycDocumentSubmitted(DomainEvent):
    customer_id: uuid.UUID
    document_id: uuid.UUID
    doc_type: str


@dataclass(frozen=True, slots=True)
class KycDocumentVerified(DomainEvent):
    customer_id: uuid.UUID
    document_id: uuid.UUID
    verified_by: uuid.UUID
    status: str


@dataclass(frozen=True, slots=True)
class CustomerApproved(DomainEvent):
    customer_id: uuid.UUID
    approved_by: uuid.UUID
    consumer_number: str


@dataclass(frozen=True, slots=True)
class ConnectionClosed(DomainEvent):
    """Fired when a customer's connection is closed for good (BR-34).

    `final_ledger_balance` is supplied by the use case, not computed here —
    the domain layer has no visibility into `accounting.invoice` data. It is
    the customer's outstanding balance (unpaid issued invoices) at the
    moment of closure, for Accounting/Cylinder Ledger settlement.
    """

    customer_id: uuid.UUID
    tenant_id: uuid.UUID
    closed_at: datetime
    final_ledger_balance: Decimal


class CustomerAddress:
    __slots__ = (
        "address_type",
        "area",
        "city",
        "district",
        "id",
        "is_primary",
        "landmark",
        "latitude",
        "line_1",
        "line_2",
        "longitude",
        "pincode",
        "state",
    )

    def __init__(
        self,
        address_id: uuid.UUID,
        line_1: str,
        address_type: str = "delivery",
        line_2: str | None = None,
        landmark: str | None = None,
        area: str | None = None,
        city: str | None = None,
        district: str | None = None,
        state: str | None = None,
        pincode: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        is_primary: bool = False,
    ) -> None:
        if not line_1.strip():
            msg = "Address line 1 cannot be empty."
            raise InvariantViolation(msg)
        if address_type not in ("delivery", "billing", "both"):
            msg = f"Invalid address type: {address_type}"
            raise InvariantViolation(msg)

        self.id = address_id
        self.address_type = address_type
        self.line_1 = line_1.strip()
        self.line_2 = line_2.strip() if line_2 else None
        self.landmark = landmark.strip() if landmark else None
        self.area = area.strip() if area else None
        self.city = city.strip() if city else None
        self.district = district.strip() if district else None
        self.state = state.strip() if state else None
        self.pincode = pincode.strip() if pincode else None
        self.latitude = latitude
        self.longitude = longitude
        self.is_primary = is_primary

    def set_primary(self, is_primary: bool) -> None:
        self.is_primary = is_primary


class KycDocument:
    __slots__ = (
        "doc_type",
        "document_number",
        "expiry_date",
        "file_url",
        "id",
        "issue_date",
        "rejection_reason",
        "verification_status",
        "verified_at",
        "verified_by",
    )

    def __init__(
        self,
        document_id: uuid.UUID,
        doc_type: str,
        document_number: str,
        file_url: str | None = None,
        issue_date: date | None = None,
        expiry_date: date | None = None,
        verification_status: str = "pending",
        verified_by: uuid.UUID | None = None,
        verified_at: datetime | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        if not doc_type.strip():
            msg = "KYC document type cannot be empty."
            raise InvariantViolation(msg)
        if not document_number.strip():
            msg = "KYC document number cannot be empty."
            raise InvariantViolation(msg)
        if verification_status not in ("pending", "verified", "rejected"):
            msg = f"Invalid KYC verification status: {verification_status}"
            raise InvariantViolation(msg)

        self.id = document_id
        self.doc_type = doc_type.strip().lower()
        self.document_number = document_number.strip()
        self.file_url = file_url
        self.issue_date = issue_date
        self.expiry_date = expiry_date
        self.verification_status = verification_status
        self.verified_by = verified_by
        self.verified_at = verified_at
        self.rejection_reason = rejection_reason

    def verify(
        self, verified_by: uuid.UUID, status: str, rejection_reason: str | None = None
    ) -> None:
        if status not in ("verified", "rejected"):
            msg = f"KYC can only be verified or rejected, got: {status}"
            raise InvariantViolation(msg)
        if status == "rejected" and not rejection_reason:
            msg = "Rejection reason is required when rejecting KYC."
            raise InvariantViolation(msg)

        self.verification_status = status
        self.rejection_reason = rejection_reason if status == "rejected" else None
        self.verified_by = verified_by
        self.verified_at = datetime.now(UTC)


class Customer(AggregateRoot):
    __slots__ = (
        "_addresses",
        "_alternate_mobile",
        "_branch_id",
        "_consumer_number",
        "_contact_person",
        "_customer_type",
        "_date_of_birth",
        "_email",
        "_full_name",
        "_identity_user_id",
        "_kyc_documents",
        "_kyc_status",
        "_lpg_subsidy_id",
        "_phone_number",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        customer_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        full_name: str,
        phone_number: str,
        consumer_number: str | None = None,
        customer_type: str = "domestic",
        kyc_status: str = "pending",
        status: str = "onboarding",
        lpg_subsidy_id: str | None = None,
        addresses: Sequence[CustomerAddress] = (),
        kyc_documents: Sequence[KycDocument] = (),
        identity_user_id: uuid.UUID | None = None,
        contact_person: str | None = None,
        alternate_mobile: str | None = None,
        email: str | None = None,
        date_of_birth: date | None = None,
        *,
        version: int = 1,
    ) -> None:
        super().__init__(customer_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id

        # Invariants validation
        if not full_name.strip() or len(full_name) > 200:
            msg = "Full name must be between 1 and 200 characters."
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if not _E164_PHONE_REGEX.match(phone_number):
            msg = f"Phone number must be in E.164 format: {phone_number}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if alternate_mobile and not _E164_PHONE_REGEX.match(alternate_mobile):
            msg = f"Alternate phone number must be in E.164 format: {alternate_mobile}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if customer_type not in ("domestic", "commercial", "industrial", "government"):
            msg = f"Invalid customer type: {customer_type}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if kyc_status not in ("pending", "verified", "rejected", "expired"):
            msg = f"Invalid KYC status: {kyc_status}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if status not in (
            "onboarding",
            "pending_approval",
            "active",
            "inactive",
            "blocked",
            "closed",
        ):
            msg = f"Invalid customer status: {status}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if status not in ("onboarding", "pending_approval") and not consumer_number:
            msg = "Consumer number is required for active/inactive/blocked/closed customers."
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if lpg_subsidy_id is not None and not _LPG_SUBSIDY_ID_REGEX.match(lpg_subsidy_id):
            msg = f"LPG subsidy ID must be exactly 17 digits: {lpg_subsidy_id}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if customer_type == "commercial" and not contact_person:
            msg = "Contact person is required for commercial customers."
            raise InvariantViolation(msg, customer_id=str(customer_id))

        self._consumer_number = consumer_number.strip() if consumer_number else None
        self._full_name = full_name.strip()
        self._phone_number = phone_number
        self._customer_type = customer_type
        self._kyc_status = kyc_status
        self._status = status
        self._lpg_subsidy_id = lpg_subsidy_id
        self._addresses = list(addresses)
        self._kyc_documents = list(kyc_documents)
        self._identity_user_id = identity_user_id
        self._contact_person = contact_person.strip() if contact_person else None
        self._alternate_mobile = alternate_mobile
        self._email = email.strip() if email else None
        self._date_of_birth = date_of_birth

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def consumer_number(self) -> str | None:
        return self._consumer_number

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def phone_number(self) -> str:
        return self._phone_number

    @property
    def customer_type(self) -> str:
        return self._customer_type

    @property
    def kyc_status(self) -> str:
        return self._kyc_status

    @property
    def status(self) -> str:
        return self._status

    @property
    def lpg_subsidy_id(self) -> str | None:
        return self._lpg_subsidy_id

    @property
    def addresses(self) -> list[CustomerAddress]:
        return list(self._addresses)

    @property
    def kyc_documents(self) -> list[KycDocument]:
        return list(self._kyc_documents)

    @property
    def identity_user_id(self) -> uuid.UUID | None:
        return self._identity_user_id

    @property
    def contact_person(self) -> str | None:
        return self._contact_person

    @property
    def alternate_mobile(self) -> str | None:
        return self._alternate_mobile

    @property
    def email(self) -> str | None:
        return self._email

    @property
    def date_of_birth(self) -> date | None:
        return self._date_of_birth

    def link_identity_user(self, identity_user_id: uuid.UUID) -> None:
        """Associate this customer profile with an identity user account."""
        self._identity_user_id = identity_user_id

    def change_status(self, new_status: str) -> None:
        if new_status not in (
            "onboarding",
            "pending_approval",
            "active",
            "inactive",
            "blocked",
            "closed",
        ):
            msg = f"Invalid status: {new_status}"
            raise InvariantViolation(msg, customer_id=str(self.id))

        if self._status == "closed" and new_status != "closed":
            msg = "Cannot reactivate a closed connection."
            raise InvariantViolation(msg, customer_id=str(self.id))

        old_status = self._status
        self._status = new_status
        self.record_event(
            CustomerStatusChanged(
                customer_id=self.id,
                old_status=old_status,
                new_status=new_status,
            )
        )

    def close_connection(self, final_ledger_balance: Decimal) -> None:
        """Close this connection for good (BR-34, D-21).

        `change_status`'s own terminal-state guard only blocks *reactivating*
        a closed connection (`new_status != "closed"`) — closing an
        already-closed one again would silently pass it and re-fire both
        events with a freshly (re)computed balance. Guarded explicitly here
        instead, matching how every other terminal state in this codebase
        (`Employee`'s `inactive`, `Order`'s `cancelled`/`closed`) rejects
        *any* further transition, not just reactivation.
        """
        if self._status == "closed":
            msg = "Connection is already closed."
            raise InvariantViolation(msg, customer_id=str(self.id))

        self.change_status("closed")
        self.record_event(
            ConnectionClosed(
                customer_id=self.id,
                tenant_id=self._tenant_id,
                closed_at=datetime.now(UTC),
                final_ledger_balance=final_ledger_balance,
            )
        )

    def add_address(
        self,
        line_1: str,
        address_type: str = "delivery",
        line_2: str | None = None,
        landmark: str | None = None,
        area: str | None = None,
        city: str | None = None,
        district: str | None = None,
        state: str | None = None,
        pincode: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> uuid.UUID:
        address_id = uuid.uuid4()
        is_first = len(self._addresses) == 0
        addr = CustomerAddress(
            address_id=address_id,
            line_1=line_1,
            address_type=address_type,
            line_2=line_2,
            landmark=landmark,
            area=area,
            city=city,
            district=district,
            state=state,
            pincode=pincode,
            latitude=latitude,
            longitude=longitude,
            is_primary=is_first,
        )
        self._addresses.append(addr)
        self.record_event(
            AddressAdded(customer_id=self.id, address_id=address_id, address_line=line_1)
        )
        return address_id

    def set_primary_address(self, address_id: uuid.UUID) -> None:
        target = next((a for a in self._addresses if a.id == address_id), None)
        if not target:
            msg = f"Address {address_id} not found."
            raise InvariantViolation(msg, customer_id=str(self.id))

        for addr in self._addresses:
            addr.set_primary(addr.id == address_id)

        self.record_event(PrimaryAddressSet(customer_id=self.id, address_id=address_id))

    def submit_kyc(
        self,
        doc_type: str,
        document_number: str,
        file_url: str | None = None,
        issue_date: date | None = None,
        expiry_date: date | None = None,
    ) -> uuid.UUID:
        doc_id = uuid.uuid4()
        doc = KycDocument(
            document_id=doc_id,
            doc_type=doc_type,
            document_number=document_number,
            file_url=file_url,
            issue_date=issue_date,
            expiry_date=expiry_date,
            verification_status="pending",
        )
        self._kyc_documents.append(doc)
        self._kyc_status = "pending"
        self.record_event(
            KycDocumentSubmitted(customer_id=self.id, document_id=doc_id, doc_type=doc_type)
        )
        return doc_id

    def verify_kyc(
        self,
        doc_id: uuid.UUID,
        verified_by: uuid.UUID,
        status: str,
        rejection_reason: str | None = None,
    ) -> None:
        target = next((d for d in self._kyc_documents if d.id == doc_id), None)
        if not target:
            msg = f"KYC document {doc_id} not found."
            raise InvariantViolation(msg, customer_id=str(self.id))

        target.verify(verified_by, status, rejection_reason)

        # Recalculate aggregate KYC status based on current documents status
        if status == "verified":
            # Check if all required docs are verified? For now just set verified if this one is,
            # but ideally we check if *all* are verified. Let's keep existing logic.
            # (Approval use-case will do the thorough check).
            self._kyc_status = "verified"
        else:
            self._kyc_status = "rejected"

        self.record_event(
            KycDocumentVerified(
                customer_id=self.id,
                document_id=doc_id,
                verified_by=verified_by,
                status=status,
            )
        )

    def approve(self, approved_by: uuid.UUID, consumer_number: str) -> None:
        if self._status not in ("onboarding", "pending_approval"):
            msg = f"Cannot approve customer in status {self._status}"
            raise InvariantViolation(msg, customer_id=str(self.id))

        if not consumer_number.strip():
            msg = "Consumer number must be provided on approval."
            raise InvariantViolation(msg, customer_id=str(self.id))

        self._consumer_number = consumer_number.strip()
        self._status = "active"

        self.record_event(
            CustomerApproved(
                customer_id=self.id, approved_by=approved_by, consumer_number=self._consumer_number
            )
        )
