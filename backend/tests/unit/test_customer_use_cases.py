from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.customer.use_cases import (
    AddCustomerAddressCommand,
    AddCustomerAddressUseCase,
    CloseCustomerConnectionCommand,
    CloseCustomerConnectionUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    SubmitKycDocumentCommand,
    SubmitKycDocumentUseCase,
    VerifyKycDocumentCommand,
    VerifyKycDocumentUseCase,
)
from lpg.domain.customer.customer import Customer


@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.register_aggregate = MagicMock()
    return uow


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_phone = AsyncMock(return_value=None)
    repo.get_by_consumer_number = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_sequence():
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="CN-999")
    return sequence


async def test_register_customer_success(mock_repo, mock_uow):
    use_case = RegisterCustomerUseCase(mock_repo, mock_uow)
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    command = RegisterCustomerCommand(
        tenant_id=tenant_id,
        branch_id=branch_id,
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
        customer_type="commercial",
        contact_person="Manager",
        line_1="123 Road",
    )

    customer = await use_case.execute(command)

    assert customer.full_name == "Jane Doe"
    assert customer.customer_type == "commercial"
    assert len(customer.addresses) == 1
    assert customer.addresses[0].line_1 == "123 Road"
    mock_repo.save.assert_called_once_with(customer)
    mock_uow.commit.assert_called_once()


async def test_register_customer_duplicate_phone(mock_repo, mock_uow):
    mock_repo.get_by_phone.return_value = MagicMock(spec=Customer)
    use_case = RegisterCustomerUseCase(mock_repo, mock_uow)

    command = RegisterCustomerCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
    )

    with pytest.raises(ConflictError):
        await use_case.execute(command)


async def test_add_address(mock_repo, mock_uow):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
    )
    mock_repo.get_by_id.return_value = customer
    use_case = AddCustomerAddressUseCase(mock_repo, mock_uow)

    command = AddCustomerAddressCommand(
        customer_id=customer.id,
        line_1="New Address St",
    )

    await use_case.execute(command)

    assert len(customer.addresses) == 1
    assert customer.addresses[0].line_1 == "New Address St"
    mock_repo.save.assert_called_once_with(customer)
    mock_uow.commit.assert_called_once()


async def test_submit_kyc(mock_repo, mock_uow):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
    )
    mock_repo.get_by_id.return_value = customer
    use_case = SubmitKycDocumentUseCase(mock_repo, mock_uow)

    command = SubmitKycDocumentCommand(
        customer_id=customer.id,
        doc_type="voter_id",
        document_number="VOTER-REF",
    )

    doc_id = await use_case.execute(command)
    assert len(customer.kyc_documents) == 1
    assert customer.kyc_documents[0].id == doc_id
    assert customer.kyc_documents[0].doc_type == "voter_id"
    assert customer.kyc_status == "pending"


async def test_verify_kyc_auto_approves_the_account_when_fully_verified(
    mock_repo, mock_uow, mock_sequence
):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        full_name="Jane Doe",
        phone_number="+1234567890",
        # status defaults to "onboarding" — no consumer_number yet, matching
        # a real just-registered customer whose only document is pending.
    )
    doc_id = customer.submit_kyc("pan", document_number="PAN-REF")
    mock_repo.get_by_id.return_value = customer
    verifier_id = uuid.uuid4()
    use_case = VerifyKycDocumentUseCase(mock_repo, mock_uow, mock_sequence)

    command = VerifyKycDocumentCommand(
        customer_id=customer.id,
        doc_id=doc_id,
        verified_by=verifier_id,
        status="verified",
    )

    await use_case.execute(command)

    assert customer.kyc_status == "verified"
    # Verifying the last outstanding document also completes onboarding —
    # there is no separate UI action that ever calls the standalone
    # approve-customer endpoint, so this is what actually activates the
    # account in practice.
    assert customer.status == "active"
    assert customer.consumer_number == "CN-999"
    mock_sequence.next.assert_awaited_once()


async def test_verify_kyc_does_not_auto_approve_on_rejection(mock_repo, mock_uow, mock_sequence):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        full_name="Jane Doe",
        phone_number="+1234567890",
    )
    doc_id = customer.submit_kyc("pan", document_number="PAN-REF")
    mock_repo.get_by_id.return_value = customer
    use_case = VerifyKycDocumentUseCase(mock_repo, mock_uow, mock_sequence)

    command = VerifyKycDocumentCommand(
        customer_id=customer.id,
        doc_id=doc_id,
        verified_by=uuid.uuid4(),
        status="rejected",
        rejection_reason="Blurry photo",
    )

    await use_case.execute(command)

    assert customer.kyc_status == "rejected"
    assert customer.status == "onboarding"
    mock_sequence.next.assert_not_awaited()


async def test_verify_kyc_does_not_auto_approve_while_another_document_is_still_pending(
    mock_repo, mock_uow, mock_sequence
):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        full_name="Jane Doe",
        phone_number="+1234567890",
    )
    aadhaar_id = customer.submit_kyc("aadhaar", document_number="AADHAAR-REF")
    customer.submit_kyc("pan", document_number="PAN-REF")  # still pending
    mock_repo.get_by_id.return_value = customer
    use_case = VerifyKycDocumentUseCase(mock_repo, mock_uow, mock_sequence)

    command = VerifyKycDocumentCommand(
        customer_id=customer.id,
        doc_id=aadhaar_id,
        verified_by=uuid.uuid4(),
        status="verified",
    )

    await use_case.execute(command)

    assert customer.kyc_status == "pending"
    assert customer.status == "onboarding"
    mock_sequence.next.assert_not_awaited()


async def test_verify_kyc_does_not_re_approve_an_already_active_customer(
    mock_repo, mock_uow, mock_sequence
):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
        status="active",
    )
    doc_id = customer.submit_kyc("pan", document_number="PAN-REF")
    mock_repo.get_by_id.return_value = customer
    use_case = VerifyKycDocumentUseCase(mock_repo, mock_uow, mock_sequence)

    command = VerifyKycDocumentCommand(
        customer_id=customer.id,
        doc_id=doc_id,
        verified_by=uuid.uuid4(),
        status="verified",
    )

    await use_case.execute(command)

    assert customer.status == "active"
    assert customer.consumer_number == "CN-123"  # unchanged, not reassigned
    mock_sequence.next.assert_not_awaited()


@pytest.fixture
def mock_invoice_repo():
    repo = MagicMock()
    repo.get_outstanding_balance = AsyncMock(return_value=Decimal("0"))
    return repo


async def test_close_customer_connection_success(mock_repo, mock_invoice_repo, mock_uow):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
        status="active",
    )
    mock_repo.get_by_id.return_value = customer
    mock_invoice_repo.get_outstanding_balance = AsyncMock(return_value=Decimal("275.50"))
    use_case = CloseCustomerConnectionUseCase(mock_repo, mock_invoice_repo, mock_uow)

    await use_case.execute(CloseCustomerConnectionCommand(customer_id=customer.id))

    assert customer.status == "closed"
    mock_invoice_repo.get_outstanding_balance.assert_called_once_with(customer.id)
    mock_repo.save.assert_called_once_with(customer)
    mock_uow.commit.assert_called_once()


async def test_close_customer_connection_raises_when_not_found(
    mock_repo, mock_invoice_repo, mock_uow
):
    mock_repo.get_by_id.return_value = None
    use_case = CloseCustomerConnectionUseCase(mock_repo, mock_invoice_repo, mock_uow)

    with pytest.raises(NotFoundError):
        await use_case.execute(CloseCustomerConnectionCommand(customer_id=uuid.uuid4()))

    mock_repo.save.assert_not_called()
    mock_uow.commit.assert_not_called()
