"""DO-02/DO-03/DO-07: identifier formats on the customer record."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import BusinessRuleViolation, InvariantViolation
from lpg.domain.customer.customer import (
    AddressNotFoundError,
    Customer,
    CustomerNotEligibleToOrderError,
)
from lpg.domain.customer.identifiers import (
    InvalidIdentifierError,
    gstin_check_character,
    normalize_gstin,
    normalize_kyc_document_number,
    normalize_pincode,
    verhoeff_check_digit,
    verhoeff_is_valid,
)

VALID_AADHAAR = "234123412346"


def _customer(**overrides: object) -> Customer:
    fields: dict[str, object] = {
        "customer_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "full_name": "Meena Iyer",
        "phone_number": "+919876543210",
    }
    fields.update(overrides)
    return Customer(**fields)  # type: ignore[arg-type]


class TestAadhaar:
    def test_a_short_number_is_rejected(self) -> None:
        with pytest.raises(InvalidIdentifierError, match="12-digit"):
            normalize_kyc_document_number("aadhaar", "1234")

    def test_a_wrong_check_digit_is_rejected(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            normalize_kyc_document_number("aadhaar", "234123412345")

    def test_a_number_starting_with_0_or_1_is_rejected(self) -> None:
        base = "12341234123"
        with pytest.raises(InvalidIdentifierError):
            normalize_kyc_document_number("aadhaar", base + verhoeff_check_digit(base))

    def test_spaces_are_removed(self) -> None:
        assert normalize_kyc_document_number("Aadhaar", "2341 2341 2346") == VALID_AADHAAR

    def test_check_digit_round_trips(self) -> None:
        base = "98769876987"
        assert verhoeff_is_valid(base + verhoeff_check_digit(base))


class TestOtherDocuments:
    @pytest.mark.parametrize(
        ("doc_type", "number", "stored"),
        [
            ("pan", "abcpe1234f", "ABCPE1234F"),
            ("voter_id", "ABC 1234567", "ABC1234567"),
            ("passport", "k1234567", "K1234567"),
            ("driving_license", "MH12 20110012345", "MH1220110012345"),
        ],
    )
    def test_valid_numbers_are_normalized(self, doc_type: str, number: str, stored: str) -> None:
        assert normalize_kyc_document_number(doc_type, number) == stored

    @pytest.mark.parametrize(
        ("doc_type", "number"),
        [
            ("pan", "ABCDE1234F"),  # 4th letter is not a PAN holder type
            ("pan", "ABCPE12345"),
            ("voter_id", "AB12345678"),
            ("passport", "12345678"),
            ("driving_license", "1234"),
        ],
    )
    def test_invalid_numbers_are_rejected(self, doc_type: str, number: str) -> None:
        with pytest.raises(InvalidIdentifierError):
            normalize_kyc_document_number(doc_type, number)

    def test_an_unknown_document_type_is_rejected(self) -> None:
        with pytest.raises(InvalidIdentifierError, match="Unsupported"):
            normalize_kyc_document_number("library_card", "X1")


class TestGstinAndPincode:
    def test_published_gstins_pass_the_check_character(self) -> None:
        assert normalize_gstin("27aapfu0939f1zv") == "27AAPFU0939F1ZV"
        assert gstin_check_character("29AAGCB7383J1Z") == "4"

    @pytest.mark.parametrize("value", ["27AAPFU0939F1ZA", "99AAPFU0939F1ZV", "27AAPFU0939F"])
    def test_invalid_gstins_are_rejected(self, value: str) -> None:
        with pytest.raises(InvalidIdentifierError):
            normalize_gstin(value)

    @pytest.mark.parametrize("value", ["012345", "50001", "5000166", "50A016"])
    def test_invalid_pincodes_are_rejected(self, value: str) -> None:
        with pytest.raises(InvalidIdentifierError):
            normalize_pincode(value)


class TestCustomerRules:
    def test_kyc_submission_rejects_an_invalid_aadhaar(self) -> None:
        customer = _customer()
        with pytest.raises(InvalidIdentifierError):
            customer.submit_kyc("aadhaar", "1234")
        assert customer.kyc_documents == []

    def test_kyc_submission_rejects_an_already_expired_document(self) -> None:
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        with pytest.raises(InvariantViolation, match="expired"):
            _customer().submit_kyc("passport", "K1234567", expiry_date=yesterday)

    def test_an_address_needs_city_and_a_valid_pincode(self) -> None:
        customer = _customer()
        with pytest.raises(InvariantViolation, match="City"):
            customer.add_address("QA Office, Begumpet, Hyderabad 500016")
        with pytest.raises(InvalidIdentifierError):
            customer.add_address("QA Office", city="Hyderabad", pincode="5000")
        with pytest.raises(InvariantViolation, match="both latitude and longitude"):
            customer.add_address("QA Office", city="Hyderabad", pincode="500016", latitude=17.4)
        address_id = customer.add_address(
            "QA Office", area="Begumpet", city="Hyderabad", pincode=" 500016 "
        )
        stored = customer.address(address_id)
        assert stored.pincode == "500016"
        assert stored.one_line == "QA Office, Begumpet, Hyderabad, 500016"

    def test_removing_the_primary_address_promotes_the_next(self) -> None:
        customer = _customer()
        first = customer.add_address("Home", city="Hyderabad", pincode="500016")
        second = customer.add_address("Office", city="Hyderabad", pincode="500001")
        customer.remove_address(first)
        assert [a.id for a in customer.addresses] == [second]
        assert customer.addresses[0].is_primary

    def test_the_only_address_cannot_be_removed(self) -> None:
        customer = _customer()
        only = customer.add_address("Home", city="Hyderabad", pincode="500016")
        with pytest.raises(BusinessRuleViolation):
            customer.remove_address(only)

    def test_another_customers_address_is_not_found(self) -> None:
        with pytest.raises(AddressNotFoundError):
            _customer().address(uuid.uuid4())

    def test_gstin_is_only_for_business_customers(self) -> None:
        with pytest.raises(InvariantViolation, match="GSTIN"):
            _customer(gstin="27AAPFU0939F1ZV")
        business = _customer(
            customer_type="commercial",
            full_name="Bharat Ceramics",
            contact_person="R. Rao",
            gstin="27aapfu0939f1zv",
        )
        assert business.gstin == "27AAPFU0939F1ZV"
        assert business.is_business

    @pytest.mark.parametrize(
        ("status", "kyc_status"),
        [("blocked", "verified"), ("inactive", "verified"), ("active", "expired")],
    )
    def test_only_active_kyc_valid_customers_can_order(self, status: str, kyc_status: str) -> None:
        customer = _customer(status=status, kyc_status=kyc_status, consumer_number="CN-000001")
        with pytest.raises(CustomerNotEligibleToOrderError):
            customer.ensure_can_place_orders()

    def test_an_active_verified_customer_can_order(self) -> None:
        _customer(
            status="active", kyc_status="verified", consumer_number="CN-000001"
        ).ensure_can_place_orders()
