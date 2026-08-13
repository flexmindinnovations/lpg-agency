from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Sequence

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


class CustomerAddress:
    def __init__(
        self,
        address_id: uuid.UUID,
        address_line: str,
        latitude: float | None = None,
        longitude: float | None = None,
        is_primary: bool = False,
    ) -> None:
        if not address_line.strip():
            msg = "Address line cannot be empty."
            raise InvariantViolation(msg)

        self.id = address_id
        self.address_line = address_line.strip()
        self.latitude = latitude
        self.longitude = longitude
        self.is_primary = is_primary

    def set_primary(self, is_primary: bool) -> None:
        self.is_primary = is_primary


class KycDocument:
    def __init__(
        self,
        document_id: uuid.UUID,
        doc_type: str,
        doc_reference: str,
        verification_status: str = "pending",
        verified_by: uuid.UUID | None = None,
        verified_at: datetime | None = None,
    ) -> None:
        if not doc_type.strip():
            msg = "KYC document type cannot be empty."
            raise InvariantViolation(msg)
        if not doc_reference.strip():
            msg = "KYC document reference cannot be empty."
            raise InvariantViolation(msg)
        if verification_status not in ("pending", "verified", "rejected"):
            msg = f"Invalid KYC verification status: {verification_status}"
            raise InvariantViolation(msg)

        self.id = document_id
        self.doc_type = doc_type.strip().lower()
        self.doc_reference = doc_reference.strip()
        self.verification_status = verification_status
        self.verified_by = verified_by
        self.verified_at = verified_at

    def verify(self, verified_by: uuid.UUID, status: str) -> None:
        if status not in ("verified", "rejected"):
            msg = f"KYC can only be verified or rejected, got: {status}"
            raise InvariantViolation(msg)
        self.verification_status = status
        self.verified_by = verified_by
        self.verified_at = datetime.now(UTC)


class Customer(AggregateRoot):
    __slots__ = (
        "_addresses",
        "_branch_id",
        "_consumer_number",
        "_customer_type",
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
        consumer_number: str,
        full_name: str,
        phone_number: str,
        customer_type: str = "domestic",
        kyc_status: str = "pending",
        status: str = "active",
        lpg_subsidy_id: str | None = None,
        addresses: Sequence[CustomerAddress] = (),
        kyc_documents: Sequence[KycDocument] = (),
        identity_user_id: uuid.UUID | None = None,
        *,
        version: int = 1,
    ) -> None:
        super().__init__(customer_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id

        # Invariants validation
        if not consumer_number.strip():
            msg = "Consumer number cannot be empty."
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if not full_name.strip() or len(full_name) > 200:
            msg = "Full name must be between 1 and 200 characters."
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if not _E164_PHONE_REGEX.match(phone_number):
            msg = f"Phone number must be in E.164 format: {phone_number}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if customer_type not in ("domestic", "commercial", "industrial", "government"):
            msg = f"Invalid customer type: {customer_type}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if kyc_status not in ("pending", "verified", "rejected", "expired"):
            msg = f"Invalid KYC status: {kyc_status}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if status not in ("active", "inactive", "blocked", "closed"):
            msg = f"Invalid customer status: {status}"
            raise InvariantViolation(msg, customer_id=str(customer_id))
        if lpg_subsidy_id is not None and not _LPG_SUBSIDY_ID_REGEX.match(lpg_subsidy_id):
            msg = f"LPG subsidy ID must be exactly 17 digits: {lpg_subsidy_id}"
            raise InvariantViolation(msg, customer_id=str(customer_id))

        self._consumer_number = consumer_number.strip()
        self._full_name = full_name.strip()
        self._phone_number = phone_number
        self._customer_type = customer_type
        self._kyc_status = kyc_status
        self._status = status
        self._lpg_subsidy_id = lpg_subsidy_id
        self._addresses = list(addresses)
        self._kyc_documents = list(kyc_documents)
        self._identity_user_id = identity_user_id

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def consumer_number(self) -> str:
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

    def link_identity_user(self, identity_user_id: uuid.UUID) -> None:
        """Associate this customer profile with an identity user account."""
        self._identity_user_id = identity_user_id

    def change_status(self, new_status: str) -> None:
        if new_status not in ("active", "inactive", "blocked", "closed"):
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

    def add_address(
        self,
        address_line: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> uuid.UUID:
        address_id = uuid.uuid4()
        is_first = len(self._addresses) == 0
        addr = CustomerAddress(
            address_id=address_id,
            address_line=address_line,
            latitude=latitude,
            longitude=longitude,
            is_primary=is_first,
        )
        self._addresses.append(addr)
        self.record_event(
            AddressAdded(customer_id=self.id, address_id=address_id, address_line=address_line)
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

    def submit_kyc(self, doc_type: str, doc_reference: str) -> uuid.UUID:
        doc_id = uuid.uuid4()
        doc = KycDocument(
            document_id=doc_id,
            doc_type=doc_type,
            doc_reference=doc_reference,
            verification_status="pending",
        )
        self._kyc_documents.append(doc)
        self._kyc_status = "pending"
        self.record_event(
            KycDocumentSubmitted(customer_id=self.id, document_id=doc_id, doc_type=doc_type)
        )
        return doc_id

    def verify_kyc(self, doc_id: uuid.UUID, verified_by: uuid.UUID, status: str) -> None:
        target = next((d for d in self._kyc_documents if d.id == doc_id), None)
        if not target:
            msg = f"KYC document {doc_id} not found."
            raise InvariantViolation(msg, customer_id=str(self.id))

        target.verify(verified_by, status)

        # Recalculate aggregate KYC status based on current documents status
        if status == "verified":
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
