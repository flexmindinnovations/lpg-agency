"""`WeighmentRecord` — Weighment Part 2 (`planning/features/
20-regulatory-compliance` subsystem 1). Append-only evidence that a
cylinder-weight check happened: MDG 2022 cl. 1.2(iv) requires 10% of filled
cylinders sampled at goods receipt; cl. 1.4(c)(d) requires 100% checked
before load-out.

A plain frozen entity, not an `AggregateRoot` — it never changes after
creation (no replace/verify/status transition to model), the same shape
`GoodsReceiptNoteEntry`/`ReconciliationRecordEntry`
(`application/inventory/ports.py`) already use for this codebase's other
append-only ledger rows. Validation lives in `__post_init__`; the pass/fail
policy is a free function (`compute_weighment_result`), not baked into the
class, so a future MDG edition with a different rule (e.g. percentage-based
rather than any-underweight-fails) is a one-function change.

Batch-level, not per-serial: `cylinder_type_id` + counts, not a list of
individual cylinder IDs. True per-cylinder traceability needs Cylinder
Identity (subsystem 3, not built) — see the plan's own "batch-level, not
per-serial, for now" design note.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import InvariantViolation

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

WEIGHMENT_CONTEXTS: frozenset[str] = frozenset({"goods_receipt_sample", "load_out_full_check"})
WEIGHMENT_REFERENCE_TYPES: frozenset[str] = frozenset({"grn", "route"})
WEIGHMENT_RESULTS: frozenset[str] = frozenset({"pass", "fail"})


def compute_weighment_result(underweight_cylinder_count: int) -> str:
    """MDG's own remedy for an underweight find is "segregate and return in
    the same truck" (R1) — i.e. any underweight cylinder in the sample means
    the check did its job and found a problem, not that the check itself was
    invalid. Modelled here as a free function, not a `WeighmentRecord`
    method, so a future MDG edition with a different rule (e.g. a tolerance
    on the *count* of underweight cylinders, not just their presence) is a
    one-function change, not a class redesign."""
    return "fail" if underweight_cylinder_count > 0 else "pass"


@dataclass(frozen=True, slots=True)
class WeighmentRecord:
    id: uuid.UUID
    tenant_id: uuid.UUID
    scale_id: uuid.UUID
    context: str
    reference_type: str
    reference_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    total_cylinders_in_batch: int
    cylinders_checked: int
    underweight_cylinder_count: int
    tolerance_grams_applied: int
    result: str
    recorded_by: uuid.UUID
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.context not in WEIGHMENT_CONTEXTS:
            msg = f"Unknown weighment context: '{self.context}'."
            raise InvariantViolation(msg)
        if self.reference_type not in WEIGHMENT_REFERENCE_TYPES:
            msg = f"Unknown weighment reference type: '{self.reference_type}'."
            raise InvariantViolation(msg)
        if self.result not in WEIGHMENT_RESULTS:
            msg = f"Unknown weighment result: '{self.result}'."
            raise InvariantViolation(msg)
        if self.total_cylinders_in_batch <= 0:
            msg = "Total cylinders in batch must be positive."
            raise InvariantViolation(msg)
        if not (0 < self.cylinders_checked <= self.total_cylinders_in_batch):
            msg = "Cylinders checked must be positive and at most the batch total."
            raise InvariantViolation(msg)
        if self.underweight_cylinder_count < 0:
            msg = "Underweight cylinder count cannot be negative."
            raise InvariantViolation(msg)
        if self.underweight_cylinder_count > self.cylinders_checked:
            msg = "Underweight cylinder count cannot exceed the number checked."
            raise InvariantViolation(msg)
        # The "100%" in "100% checked before load-out" (MDG cl. 1.4(c)(d)) is
        # the whole point of this context — a partial load-out check
        # shouldn't be able to satisfy Part 3's dispatch gate by mistake.
        if (
            self.context == "load_out_full_check"
            and self.cylinders_checked != self.total_cylinders_in_batch
        ):
            msg = (
                "A load-out full check must cover every cylinder in the batch "
                f"({self.cylinders_checked} of {self.total_cylinders_in_batch} checked)."
            )
            raise InvariantViolation(msg)
