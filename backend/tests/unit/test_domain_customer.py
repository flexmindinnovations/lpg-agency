from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.customer.customer import ConnectionClosed, Customer, CustomerStatusChanged


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
    assert customer.status == "onboarding"


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
    addr_id = customer.add_address("123 Main St", latitude=12.34, longitude=56.78)
    assert len(customer.addresses) == 1
    assert customer.addresses[0].id == addr_id
    assert customer.addresses[0].line_1 == "123 Main St"
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


def test_resubmitting_the_same_doc_type_replaces_the_prior_document():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    first_id = customer.submit_kyc("aadhaar", "111122223333", file_url="blob/first.png")

    second_id = customer.submit_kyc("aadhaar", "444455556666", file_url="blob/second.png")

    assert len(customer.kyc_documents) == 1
    assert customer.kyc_documents[0].id == second_id
    assert customer.kyc_documents[0].id != first_id
    assert customer.kyc_documents[0].document_number == "444455556666"
    assert customer.kyc_documents[0].file_url == "blob/second.png"


def test_a_different_doc_type_is_added_alongside_not_replacing():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    customer.submit_kyc("aadhaar", "111122223333")

    customer.submit_kyc("pan", "ABCDE1234F")

    assert {d.doc_type for d in customer.kyc_documents} == {"aadhaar", "pan"}


def test_verifying_one_document_does_not_verify_the_whole_customer_while_another_is_pending():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    aadhaar_id = customer.submit_kyc("aadhaar", "111122223333")
    customer.submit_kyc("pan", "ABCDE1234F")  # left pending

    customer.verify_kyc(aadhaar_id, uuid.uuid4(), "verified")

    assert customer.kyc_status == "pending"


def test_rejecting_one_document_marks_the_customer_rejected_even_if_another_is_verified():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    aadhaar_id = customer.submit_kyc("aadhaar", "111122223333")
    pan_id = customer.submit_kyc("pan", "ABCDE1234F")
    verifier_id = uuid.uuid4()
    customer.verify_kyc(aadhaar_id, verifier_id, "verified")

    customer.verify_kyc(pan_id, verifier_id, "rejected", rejection_reason="Expired document")

    assert customer.kyc_status == "rejected"
    # The already-verified document's own status is untouched.
    assert customer.kyc_documents[0].verification_status == "verified"


def test_adding_a_second_doc_type_correctly_requires_it_to_be_verified_too():
    # kyc_status means "every current document is verified" — adding a
    # second document type alongside an already-verified one correctly
    # drops the aggregate back to "pending" until the new one is reviewed
    # too, without touching the first document's own verified status.
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    aadhaar_id = customer.submit_kyc("aadhaar", "111122223333")
    customer.verify_kyc(aadhaar_id, uuid.uuid4(), "verified")
    assert customer.kyc_status == "verified"

    customer.submit_kyc("pan", "ABCDE1234F")

    assert customer.kyc_status == "pending"
    assert customer.kyc_documents[0].verification_status == "verified"


def test_resubmitting_an_already_verified_doc_type_requires_re_verification():
    # Regression: submit_kyc previously appended a duplicate row and reset
    # kyc_status unconditionally either way — now it replaces the same
    # doc_type outright, and the reset to "pending" reflects that the
    # replacement document genuinely hasn't been reviewed yet.
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
    )
    aadhaar_id = customer.submit_kyc("aadhaar", "111122223333")
    customer.verify_kyc(aadhaar_id, uuid.uuid4(), "verified")
    assert customer.kyc_status == "verified"

    customer.submit_kyc("aadhaar", "999988887777")

    assert len(customer.kyc_documents) == 1
    assert customer.kyc_status == "pending"
    assert customer.kyc_documents[0].verification_status == "pending"


def test_close_connection_transitions_to_closed_and_records_both_events():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
        status="active",
    )

    customer.close_connection(Decimal("450.00"))

    assert customer.status == "closed"

    status_events = [e for e in customer.events if isinstance(e, CustomerStatusChanged)]
    assert len(status_events) == 1
    assert status_events[0].old_status == "active"
    assert status_events[0].new_status == "closed"

    closed_events = [e for e in customer.events if isinstance(e, ConnectionClosed)]
    assert len(closed_events) == 1
    assert closed_events[0].customer_id == customer.id
    assert closed_events[0].tenant_id == customer.tenant_id
    assert closed_events[0].final_ledger_balance == Decimal("450.00")


def test_close_connection_accepts_zero_balance():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
        status="active",
    )

    customer.close_connection(Decimal("0"))

    closed_events = [e for e in customer.events if isinstance(e, ConnectionClosed)]
    assert closed_events[0].final_ledger_balance == Decimal("0")


def test_close_connection_is_terminal():
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-12345",
        full_name="John Doe",
        phone_number="+1234567890",
        status="closed",
    )

    with pytest.raises(InvariantViolation, match="already closed"):
        customer.close_connection(Decimal("0"))
