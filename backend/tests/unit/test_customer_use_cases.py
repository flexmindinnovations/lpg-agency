from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import ConflictError
from lpg.application.customer.use_cases import (
    AddCustomerAddressCommand,
    AddCustomerAddressUseCase,
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


async def test_verify_kyc(mock_repo, mock_uow):
    customer = Customer(
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        consumer_number="CN-123",
        full_name="Jane Doe",
        phone_number="+1234567890",
    )
    doc_id = customer.submit_kyc("pan", document_number="PAN-REF")
    mock_repo.get_by_id.return_value = customer
    use_case = VerifyKycDocumentUseCase(mock_repo, mock_uow)

    command = VerifyKycDocumentCommand(
        customer_id=customer.id,
        doc_id=doc_id,
        verified_by=uuid.uuid4(),
        status="verified",
    )

    await use_case.execute(command)
    assert customer.kyc_status == "verified"
