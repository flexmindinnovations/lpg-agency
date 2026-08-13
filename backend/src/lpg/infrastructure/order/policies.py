"""Permissive stub implementations of `application/order/ports.py`'s
`CylinderCapPolicy`/`CreditLimitEvaluator`.

Both real checks (BR-04, BR-19) depend on data owned by modules that don't
exist yet — Cylinder Ledger (Phase 12) for a customer's current cylinder
holding count, Accounting (Phase 13) for outstanding balance. Rather than
skip the checks silently or fake a result, both ports are wired for real
(dependency-injected into `ConfirmOrderUseCase`, unit-tested for this exact
no-op behaviour) with a stub adapter that simply allows every booking. A
`git grep PermissiveCylinderCapPolicy`/`PermissiveCreditLimitEvaluator` in
Phase 12/13 finds the one call site each to replace with a real adapter —
the use case and port contract never change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal


class PermissiveCylinderCapPolicy:
    # Every argument below is unused by design (see module docstring) — the
    # full Protocol signature is kept, not collapsed to `**_kwargs`, so this
    # class stays structurally checkable against `CylinderCapPolicy`.
    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,  # noqa: ARG002
        customer_id: uuid.UUID,  # noqa: ARG002
        customer_type: str,  # noqa: ARG002
        requested_lines: Sequence[tuple[uuid.UUID, int]],  # noqa: ARG002
    ) -> None:
        """No-op — BR-04 has no data source until Cylinder Ledger (Phase 12)."""
        return


class PermissiveCreditLimitEvaluator:
    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,  # noqa: ARG002
        customer_id: uuid.UUID,  # noqa: ARG002
        order_total: Decimal,  # noqa: ARG002
    ) -> None:
        """No-op — BR-19 has no data source until Accounting (Phase 13)."""
        return
