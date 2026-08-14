import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.cylinder_ledger.cylinder_ledger import (
    CylinderLedger,
    NegativeBalanceError,
)


def test_cylinder_ledger_initialization():
    ledger_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    ledger = CylinderLedger(
        cylinder_ledger_id=ledger_id,
        customer_id=customer_id,
        tenant_id=tenant_id
    )

    assert ledger.id == ledger_id
    assert ledger.customer_id == customer_id
    assert ledger.tenant_id == tenant_id
    assert ledger.balances == {}
    assert len(ledger.pending_transactions) == 0

def test_record_delivery_increases_balance():
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4()
    )
    cylinder_type_id = uuid.uuid4()
    performed_by = uuid.uuid4()

    ledger.record_delivery(cylinder_type_id, 2, performed_by=performed_by)

    assert ledger.balance_of(cylinder_type_id) == 2
    assert len(ledger.pending_transactions) == 1
    assert ledger.pending_transactions[0].transaction_type == "delivery"
    assert ledger.pending_transactions[0].quantity == 2

def test_record_collection_decreases_balance():
    cylinder_type_id = uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        balances={cylinder_type_id: 5}
    )
    performed_by = uuid.uuid4()

    ledger.record_collection(cylinder_type_id, 2, performed_by=performed_by)

    assert ledger.balance_of(cylinder_type_id) == 3
    assert len(ledger.pending_transactions) == 1
    assert ledger.pending_transactions[0].transaction_type == "collection"
    assert ledger.pending_transactions[0].quantity == -2

def test_negative_balance_raises_error():
    cylinder_type_id = uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        balances={cylinder_type_id: 1}
    )

    with pytest.raises(NegativeBalanceError):
        ledger.record_collection(cylinder_type_id, 2, performed_by=uuid.uuid4())

def test_zero_quantity_raises_error():
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4()
    )

    with pytest.raises(InvariantViolation, match="Delivery quantity must be > 0"):
        ledger.record_delivery(uuid.uuid4(), 0, performed_by=uuid.uuid4())

    with pytest.raises(InvariantViolation, match="Collection quantity must be > 0"):
        ledger.record_collection(uuid.uuid4(), 0, performed_by=uuid.uuid4())

def test_adjust_positive_and_negative():
    cylinder_type_id = uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        balances={cylinder_type_id: 5}
    )

    ledger.adjust(cylinder_type_id, -2, performed_by=uuid.uuid4(), reason="Damaged")
    assert ledger.balance_of(cylinder_type_id) == 3

    ledger.adjust(cylinder_type_id, 3, performed_by=uuid.uuid4(), reason="Found")
    assert ledger.balance_of(cylinder_type_id) == 6

def test_set_initial_balance():
    cylinder_type_id = uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4()
    )

    ledger.set_initial_balance(cylinder_type_id, 10, performed_by=uuid.uuid4())
    assert ledger.balance_of(cylinder_type_id) == 10

def test_set_initial_balance_fails_if_already_set():
    cylinder_type_id = uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        balances={cylinder_type_id: 5}
    )

    with pytest.raises(InvariantViolation, match="Initial balance can only be set when current balance is 0"):
        ledger.set_initial_balance(cylinder_type_id, 10, performed_by=uuid.uuid4())
