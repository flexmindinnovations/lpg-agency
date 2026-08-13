import uuid

from lpg.application.cylinder_ledger.ports import CylinderLedgerRepository
from lpg.application.order.ports import OrderRepository
from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger


class AppendLedgerTransactionsFromOrderUseCase:
    """Appends transactions to the customer's cylinder ledger based on a delivered order."""

    def __init__(
        self,
        ledger_repository: CylinderLedgerRepository,
        order_repository: OrderRepository,
    ) -> None:
        self._ledger_repository = ledger_repository
        self._order_repository = order_repository

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        performed_by: uuid.UUID,
    ) -> None:
        # Tenant scoping is enforced by RLS on the session, not by a
        # repository argument -- see SqlAlchemyOrderRepository's docstring.
        order = await self._order_repository.get_by_id(order_id)
        if not order:
            return  # Order deleted/not found

        if order.status != "delivered" and order.status != "closed":
            # Ledger is only updated when the order is successfully delivered
            return

        # 2. Load or initialize the Ledger
        ledger = await self._ledger_repository.get_by_customer_id(tenant_id, order.customer_id)

        # 3. Apply transactions for each line
        # Note: In a robust event-driven system, we'd need to ensure idempotency.
        # This can be done by checking if the reference_id (order_id) already exists
        # in the ledger's transactions or relying on the inbox/outbox idempotency logic.
        for line in order.lines:
            # Deliveries: agency gave filled cylinders to customer
            if line.quantity_delivered > 0:
                ledger.record_delivery(
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity_delivered,
                    performed_by=performed_by,
                    reference_id=order.id,
                )

            # Collections: customer gave empty cylinders back to agency
            if line.quantity_collected_empty > 0:
                ledger.record_collection(
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity_collected_empty,
                    performed_by=performed_by,
                    reference_id=order.id,
                )

        # A brand-new ledger with nothing recorded against it has nothing
        # worth persisting; anything else does.
        if ledger.version == 1 and not ledger.pending_transactions:
            return
        await self._ledger_repository.add(ledger)


class AdjustLedgerBalanceUseCase:
    """Manual adjustment of a customer's cylinder balance by staff."""

    def __init__(self, ledger_repository: CylinderLedgerRepository) -> None:
        self._ledger_repository = ledger_repository

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        delta: int,
        reason: str,
        performed_by: uuid.UUID,
    ) -> CylinderLedger:
        ledger = await self._ledger_repository.get_by_customer_id(tenant_id, customer_id)
        ledger.adjust(
            cylinder_type_id=cylinder_type_id, delta=delta, performed_by=performed_by, reason=reason
        )
        await self._ledger_repository.add(ledger)
        return ledger


class GetCylinderLedgerUseCase:
    """Gets the customer's cylinder ledger and balance."""

    def __init__(self, ledger_repository: CylinderLedgerRepository) -> None:
        self._ledger_repository = ledger_repository

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> CylinderLedger:
        return await self._ledger_repository.get_by_customer_id(tenant_id, customer_id)
