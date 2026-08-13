"""`CancellationFeeCalculator` — D-19's tenant-configurable post-dispatch fee.

Pure, no I/O. Resolves against `tenant.tenant_configuration`'s existing
`cancellation_fee_amount` key (`domain/tenant/tenant_configuration.py`,
seeded in Phase 7 in clear anticipation of this phase) via the already-
existing `TenantConfigurationResolver` — this module only defines the
`config_value` JSON shape and the arithmetic, not a new resolution
mechanism.
"""

from __future__ import annotations

from decimal import Decimal

from lpg.domain.common.base import InvariantViolation


class CancellationFeeCalculator:
    @staticmethod
    def calculate(*, config_value: dict[str, str] | None, order_total: Decimal) -> Decimal:
        """`config_value` is `{"policy_type": "flat"|"percentage", "amount": "<decimal-string>"}`.

        No configured policy (tenant hasn't set one) means no fee — silence
        is not an error here, since D-19 only says a charge "may" apply, not
        that it always must.
        """
        if config_value is None:
            return Decimal("0")

        policy_type = config_value["policy_type"]
        amount = Decimal(config_value["amount"])

        if policy_type == "flat":
            return min(amount, order_total)
        if policy_type == "percentage":
            fee = (order_total * amount / Decimal("100")).quantize(Decimal("0.01"))
            return min(fee, order_total)

        msg = f"Unknown cancellation fee policy type: {policy_type}"
        raise InvariantViolation(msg, policy_type=policy_type)
