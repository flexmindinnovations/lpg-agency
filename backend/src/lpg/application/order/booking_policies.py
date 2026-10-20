"""The real BR-04 / BR-19 checks behind `CylinderCapPolicy` and
`CreditLimitEvaluator` (they replace the permissive stubs that stood in
until the Cylinder Ledger and Accounting existed).

The arithmetic lives in `domain/order/booking_limits.py`; these classes only
gather its inputs — the tenant's configured limit for the customer's type,
the customer's cylinder holding (Cylinder Ledger), what their open orders
will still deliver, and their unpaid invoices (Accounting).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lpg.application.common.errors import CreditLimitExceededError, CylinderCapExceededError
from lpg.domain.order.booking_limits import limit_for_customer_type, projected_cylinder_holding
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal

    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.cylinder_ledger.ports import CylinderLedgerRepository
    from lpg.application.order.ports import CustomerOpenOrderReader
    from lpg.application.tenant.ports import TenantConfigurationRepository

#: `{"domestic": 2, "commercial": 10, ...}` or one number for every type.
CYLINDER_HOLDING_CAP_CONFIG_KEY = "cylinder_holding_cap"
#: Same shape; the largest unpaid amount (₹) a customer may owe once this
#: booking is billed.
CREDIT_LIMIT_CONFIG_KEY = "credit_limit_default"


async def _configured_value(
    configuration: TenantConfigurationRepository, tenant_id: uuid.UUID, key: str
) -> Any:
    entries = await configuration.list_for_tenant_and_key(tenant_id, key)
    resolved = TenantConfigurationResolver.resolve(entries, key, datetime.now(UTC))
    return resolved.config_value if resolved is not None else None


class LedgerCylinderCapPolicy:
    """BR-04: refuse a booking that would leave the customer holding more
    cylinders than their connection type allows."""

    def __init__(
        self,
        configuration: TenantConfigurationRepository,
        ledger_repository: CylinderLedgerRepository,
        open_orders: CustomerOpenOrderReader,
    ) -> None:
        self._configuration = configuration
        self._ledger_repository = ledger_repository
        self._open_orders = open_orders

    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_type: str,
        requested_lines: Sequence[tuple[uuid.UUID, int]],
        exclude_order_id: uuid.UUID | None = None,
    ) -> None:
        config_value = await _configured_value(
            self._configuration, tenant_id, CYLINDER_HOLDING_CAP_CONFIG_KEY
        )
        cap = limit_for_customer_type(config_value, customer_type)
        if cap is None:
            return
        ledger = await self._ledger_repository.get_by_customer_id(tenant_id, customer_id)
        open_quantities = await self._open_orders.open_quantities(
            customer_id, exclude_order_id=exclude_order_id
        )
        holding = projected_cylinder_holding(
            balances=ledger.balances,
            open_order_quantities=open_quantities,
            requested_lines=requested_lines,
        )
        if holding > cap:
            max_cylinders = int(cap)
            msg = (
                f"This booking would leave the customer holding {holding} cylinders; a "
                f"{customer_type} connection may hold at most {max_cylinders}. Reduce the "
                "quantity, or collect their empties first."
            )
            raise CylinderCapExceededError(
                msg,
                customer_id=str(customer_id),
                projected_holding=holding,
                cap=max_cylinders,
            )


class OutstandingBalanceCreditLimitEvaluator:
    """BR-19: refuse to confirm a booking that would take the customer's
    unpaid balance past their credit limit."""

    def __init__(
        self,
        configuration: TenantConfigurationRepository,
        invoice_repository: InvoiceRepository,
    ) -> None:
        self._configuration = configuration
        self._invoice_repository = invoice_repository

    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_type: str,
        order_total: Decimal,
    ) -> None:
        config_value = await _configured_value(
            self._configuration, tenant_id, CREDIT_LIMIT_CONFIG_KEY
        )
        limit = limit_for_customer_type(config_value, customer_type)
        if limit is None:
            return
        outstanding = await self._invoice_repository.get_outstanding_balance(customer_id)
        if outstanding + order_total > limit:
            msg = (
                f"The customer already owes ₹{outstanding:,.2f}; with this booking "
                f"(₹{order_total:,.2f}) that is over their credit limit of ₹{limit:,.2f}. "
                "Collect the outstanding amount first."
            )
            raise CreditLimitExceededError(
                msg,
                customer_id=str(customer_id),
                outstanding=str(outstanding),
                order_total=str(order_total),
                credit_limit=str(limit),
            )
