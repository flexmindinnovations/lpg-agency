from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.customer.customer import Customer


def test_customer_creation_valid():
    customer_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    customer = Customer(
        customer_id=customer_id,
        tenant_id=tenant_id,
        branch_id=branch_id,
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
        customer_type="domestic",
    )
    assert customer.id == customer_id
    assert customer.tenant_id == tenant_id
    assert customer.branch_id == branch_id
    assert customer.consumer_number == "CN-12345"
    assert customer.full_name == "John Doe"
    assert customer.phone_number == "+1234567890"
    assert customer.customer_type == "domestic"
    assert customer.kyc_status == "pending"
    assert customer.status == "active"


def test_customer_creation_invalid_phone():
    with pytest.raises(InvariantViolation) as excinfo:
        Customer(
            customer_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            branch_id=uuid.uuid4(),
            consumer_number="CN-12345",
            full_name="John Doe",
            phone_number="12345",  # missing plus sign, too short
        )
    assert "Phone number must be in E.164 format" in str(excinfo.value)


def test_customer_creation_invalid_customer_type():
    with pytest.raises(InvariantViolation) as excinfo:
        Customer(
            customer_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            branch_id=uuid.uuid4(),
            consumer_number="CN-12345",
            full_name="John Doe",
            phone_number="+1234567890",
            customer_type="premium",  # not allowed
        )
    assert "Invalid customer type" in str(excinfo.value)


def test_customer_add_address():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    addr_id = customer.add_address("123 Main St", 12.34, 56.78)
    assert len(customer.addresses) == 1
    assert customer.addresses[0].id == addr_id
    assert customer.addresses[0].address_line == "123 Main St"
    assert customer.addresses[0].is_primary is True  # first address is automatically primary

    addr_id_2 = customer.add_address("456 Oak Ave")
    addresses = customer.addresses
    assert len(addresses) == 2
    assert addresses[1].is_primary is False

    customer.set_primary_address(addr_id_2)
    addresses = customer.addresses
    assert addresses[0].is_primary is False
    assert addresses[1].is_primary is True


def test_customer_creation_with_valid_lpg_subsidy_id():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
        lpg_subsidy_id="12345678901234567",
    )
    assert customer.lpg_subsidy_id == "12345678901234567"


def test_customer_creation_lpg_subsidy_id_defaults_to_none():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    assert customer.lpg_subsidy_id is None


def test_customer_creation_invalid_lpg_subsidy_id_wrong_length():
    with pytest.raises(InvariantViolation) as excinfo:
        Customer(
            customer_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            branch_id=uuid.uuid4(),
            consumer_number="CN-12345",
            full_name="John Doe",
            phone_number="+1234567890",
            lpg_subsidy_id="123456",  # too short, must be 17 digits
        )
    assert "LPG subsidy ID must be exactly 17 digits" in str(excinfo.value)


def test_customer_creation_invalid_lpg_subsidy_id_non_numeric():
    with pytest.raises(InvariantViolation):
        Customer(
            customer_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            branch_id=uuid.uuid4(),
            consumer_number="CN-12345",
            full_name="John Doe",
            phone_number="+1234567890",
            lpg_subsidy_id="1234567890abcdefg",  # non-numeric
        )


def test_customer_kyc_flow():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    doc_id = customer.submit_kyc("aadhaar", "REF123456")
    assert customer.kyc_status == "pending"
    assert len(customer.kyc_documents) == 1
    assert customer.kyc_documents[0].verification_status == "pending"

    verifier_id = uuid.uuid4()
    customer.verify_kyc(doc_id, verifier_id, "verified")
    assert customer.kyc_status == "verified"
    assert customer.kyc_documents[0].verification_status == "verified"
    assert customer.kyc_documents[0].verified_by == verifier_id
