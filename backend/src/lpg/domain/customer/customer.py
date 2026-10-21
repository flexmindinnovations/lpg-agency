from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import (
    AggregateRoot,
    BusinessRuleViolation,
    DomainEvent,
    InvariantViolation,
)
from lpg.domain.customer.identifiers import (
    InvalidIdentifierError,
    normalize_gstin,
    normalize_kyc_document_number,
    normalize_pincode,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

# Regex for E.164 phone format validation (+ followed by 10 to 15 digits)
_E164_PHONE_REGEX = re.compile(r"^\+[1-9]\d{9,14}$")

# The nationally-standardized 17-digit LPG ID (Indane/Bharat Gas/HP Gas
# subsidy/KYC identifier) — distinct from `consumer_number`, which is the
# shorter, locally-assigned-by-the-agency number used for refill booking.
_LPG_SUBSIDY_ID_REGEX = re.compile(r"^\d{17}$")

#: Customer types that are businesses or institutions rather than
#: households. For these `full_name` is the registered business name and
#: `gstin` may be recorded for B2B GST invoices (D-03).
BUSINESS_CUSTOMER_TYPES = frozenset({"commercial", "industrial", "government"})

#: KYC states under which a customer may not place new orders.
_KYC_BLOCKING_BOOKING = frozenset({"rejected", "expired"})
#: Connection states that may book. `onboarding` stays bookable: whether a
#: customer whose KYC is still pending may take a first refill is an open
#: BR-21 policy question (docs/data/06-data-dictionary.md, "policy TBD"),
#: so the existing behaviour is kept until the business decides.
_STATUSES_ALLOWED_TO_BOOK = frozenset({"active", "onboarding"})


class CustomerNotEligibleToOrderError(BusinessRuleViolation):
    """The customer's connection or KYC does not allow a new booking."""

    error_code = "CUSTOMER_NOT_ELIGIBLE"


class AddressNotFoundError(InvariantViolation):
    """The address id is not one of this customer's current addresses."""

    error_code = "ADDRESS_NOT_FOUND"


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
class AddressUpdated(DomainEvent):
    customer_id: uuid.UUID
    address_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AddressRemoved(DomainEvent):
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

    @property
    def one_line(self) -> str:
        """The address as one line, for delivery labels and order snapshots."""
        parts = (
            self.line_1,
            self.line_2,
            self.landmark,
            self.area,
            self.city,
            self.district,
            self.state,
            self.pincode,
        )
        return ", ".join(part for part in parts if part)


def _validated_address_fields(
    *,
    line_1: str,
    city: str | None,
    pincode: str | None,
    latitude: float | None,
    longitude: float | None,
) -> str:
    """Rules for an address staff or a customer enter now (DO-07). Kept out
    of `CustomerAddress.__init__` so older rows saved before these rules
    still load. Returns the normalized PIN code.
    """
    if not line_1.strip():
        msg = "Address line 1 cannot be empty."
        raise InvariantViolation(msg, field="line_1")
    if not city or not city.strip():
        msg = "City is required for a delivery address."
        raise InvariantViolation(msg, field="city")
    if not pincode or not pincode.strip():
        msg = "PIN code is required for a delivery address."
        raise InvalidIdentifierError(msg, field="pincode")
    if (latitude is None) != (longitude is None):
        msg = "A map pin needs both latitude and longitude."
        raise InvariantViolation(msg, field="latitude")
    if latitude is not None and not -90 <= latitude <= 90:
        msg = "Latitude must be between -90 and 90."
        raise InvariantViolation(msg, field="latitude")
    if longitude is not None and not -180 <= longitude <= 180:
        msg = "Longitude must be between -180 and 180."
        raise InvariantViolation(msg, field="longitude")
    return normalize_pincode(pincode)


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
        "_gstin",
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
        gstin: str | None = None,
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
        if gstin and customer_type not in BUSINESS_CUSTOMER_TYPES:
            msg = "GSTIN can only be recorded for commercial, industrial or government customers."
            raise InvariantViolation(msg, customer_id=str(customer_id), field="gstin")

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
        self._gstin = normalize_gstin(gstin) if gstin else None

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

    @property
    def gstin(self) -> str | None:
        return self._gstin

    @property
    def is_business(self) -> bool:
        return self._customer_type in BUSINESS_CUSTOMER_TYPES

    def ensure_can_place_orders(self) -> None:
        """Inactive, blocked or closed connections, and customers whose KYC
        was rejected or has expired, may not book cylinders (BR-21, DO-11)."""
        if self._status not in _STATUSES_ALLOWED_TO_BOOK:
            label = self._status.replace("_", " ")
            msg = f"{self._full_name} cannot book cylinders while the connection is {label}."
            raise CustomerNotEligibleToOrderError(
                msg, customer_id=str(self.id), status=self._status
            )
        if self._kyc_status in _KYC_BLOCKING_BOOKING:
            msg = (
                f"{self._full_name} cannot book cylinders until their KYC is renewed "
                f"(KYC {self._kyc_status})."
            )
            raise CustomerNotEligibleToOrderError(
                msg, customer_id=str(self.id), kyc_status=self._kyc_status
            )

    def address(self, address_id: uuid.UUID) -> CustomerAddress:
        """One of this customer's current addresses, or `AddressNotFoundError`."""
        found = next((a for a in self._addresses if a.id == address_id), None)
        if found is None:
            msg = "That address does not belong to this customer."
            raise AddressNotFoundError(msg, customer_id=str(self.id), address_id=str(address_id))
        return found

    @property
    def can_get_app_login(self) -> bool:
        """Whether a Customer App login may be created for this customer on
        their first phone + OTP sign-in.

        Only a customer with no login yet whose connection is still live:
        onboarding and pending-approval customers need to sign in to finish
        KYC, while inactive, blocked and closed ones must not get a new way in.
        """
        return self._identity_user_id is None and self._status in (
            "onboarding",
            "pending_approval",
            "active",
        )

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
        pincode = _validated_address_fields(
            line_1=line_1, city=city, pincode=pincode, latitude=latitude, longitude=longitude
        )
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

    def update_address(
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
    ) -> None:
        index = next((i for i, a in enumerate(self._addresses) if a.id == address_id), None)
        if index is None:
            msg = "That address does not belong to this customer."
            raise AddressNotFoundError(msg, customer_id=str(self.id))
        pincode = _validated_address_fields(
            line_1=line_1, city=city, pincode=pincode, latitude=latitude, longitude=longitude
        )

        # Rebuild via `CustomerAddress.__init__` rather than mutating fields
        # in place, so this reuses the same validation `add_address` gets
        # (non-empty line_1, a valid address_type) instead of duplicating it.
        was_primary = self._addresses[index].is_primary
        self._addresses[index] = CustomerAddress(
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
            is_primary=was_primary,
        )
        self.record_event(AddressUpdated(customer_id=self.id, address_id=address_id))

    def remove_address(self, address_id: uuid.UUID) -> None:
        """Removes an address (soft-deleted by the repository, so past orders
        keep their snapshot). The last address cannot be removed — a
        connection always needs somewhere to deliver. Removing the primary
        address promotes the next one.
        """
        target = self.address(address_id)
        if len(self._addresses) == 1:
            msg = "Add another address before removing the only one on file."
            raise BusinessRuleViolation(msg, customer_id=str(self.id))
        self._addresses = [a for a in self._addresses if a.id != address_id]
        if target.is_primary:
            self._addresses[0].set_primary(True)
        self.record_event(AddressRemoved(customer_id=self.id, address_id=address_id))

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
        normalized_doc_type = doc_type.strip().lower()
        document_number = normalize_kyc_document_number(normalized_doc_type, document_number)
        if issue_date is not None and expiry_date is not None and expiry_date < issue_date:
            msg = "The document's expiry date cannot be before its issue date."
            raise InvariantViolation(msg, customer_id=str(self.id), field="expiry_date")
        if expiry_date is not None and expiry_date < datetime.now(UTC).date():
            msg = "This document has already expired. Ask the customer for a current one."
            raise InvariantViolation(msg, customer_id=str(self.id), field="expiry_date")
        # A resubmission of the same doc_type (a clearer photo, a fix
        # after rejection) supersedes the previous attempt rather than
        # accumulating as a duplicate — a customer only ever has one
        # *current* Aadhaar/PAN/etc. on file. A different doc_type is a
        # genuine addition (e.g. PAN alongside an existing Aadhaar), so
        # only same-type documents are replaced.
        self._kyc_documents = [d for d in self._kyc_documents if d.doc_type != normalized_doc_type]
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
        self._recompute_kyc_status()
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
        self._recompute_kyc_status()

        self.record_event(
            KycDocumentVerified(
                customer_id=self.id,
                document_id=doc_id,
                verified_by=verified_by,
                status=status,
            )
        )

    def _recompute_kyc_status(self) -> None:
        """The aggregate `kyc_status` always reflects the *current* full
        document set, recomputed from scratch, rather than being set
        piecemeal from whichever single action just happened — verified
        only when every current document is verified, rejected if any
        current document needs re-review, pending otherwise (including
        "no documents yet"). Recomputing from scratch after every
        submit/verify means it can never drift out of sync with the
        documents themselves, which piecemeal updates previously allowed:
        `verify_kyc` used to set the aggregate from just the one document
        being verified (ignoring any others), and `submit_kyc` used to
        unconditionally reset it to "pending" even when submitting an
        unrelated, already-verified document type.
        """
        if not self._kyc_documents:
            self._kyc_status = "pending"
        elif any(d.verification_status == "rejected" for d in self._kyc_documents):
            self._kyc_status = "rejected"
        elif all(d.verification_status == "verified" for d in self._kyc_documents):
            self._kyc_status = "verified"
        else:
            self._kyc_status = "pending"

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
