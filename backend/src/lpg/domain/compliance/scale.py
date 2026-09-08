"""`Scale` aggregate root — Weighment Part 1 (`planning/features/
20-regulatory-compliance`, subsystem 1). MDG 2022 cl. 1.2 requires a working,
certified digital scale of least count ≤10 g at every godown; its absence, or
an expired certificate, is itself a named Minor irregularity (R1).

Deliberately mirrors `domain/delivery/compliance_document.py`'s shape (this
codebase's established "registry with expiry" pattern) rather than inventing
a new one: `is_expired(as_of=...)`, a `replace_certificate` renewal idiom,
and the same owner-frozenset validation style — just for a scale instead of
a driver/vehicle document.

Build to **certificate validity only** — MDG does not prescribe a
reverification interval, only that the certificate be valid
(`docs/research/feature-gap-analysis.md` §7.6). No assumed periodicity is
modelled here; only `certificate_expiry_date` matters.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, date, datetime

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCALE_STATUSES: frozenset[str] = frozenset({"active", "inactive"})

#: MDG 2022 cl. 1.2(ii)(iii) — "Platform-type digital weighing scale of least
#: count ±10 g". A scale registered above this precision cannot evidence
#: compliance regardless of anything else, so this is a hard domain
#: invariant, not a soft default (unlike the weight *tolerance*, which is
#: tenant-configurable — see `TenantConfiguration.weighment_scale_least_
#: count_max_grams`, kept in sync with this constant's value of 10).
MAX_LEAST_COUNT_GRAMS = 10

# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScaleRegistered(DomainEvent):
    scale_id: uuid.UUID
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    certificate_expiry_date: date


@dataclass(frozen=True, slots=True)
class ScaleCertificateReplaced(DomainEvent):
    scale_id: uuid.UUID
    warehouse_id: uuid.UUID
    certificate_expiry_date: date


@dataclass(frozen=True, slots=True)
class ScaleStatusChanged(DomainEvent):
    scale_id: uuid.UUID
    warehouse_id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Scale(AggregateRoot):
    """A registered weighing scale at a warehouse (godown).

    Business invariants:
    - ``least_count_grams`` must be a positive integer ``<= MAX_LEAST_COUNT_GRAMS``.
    - ``certificate_expiry_date`` is required — MDG's own requirement is a
      *valid* certificate, so a scale with no certificate on file cannot be
      registered.
    - ``status`` transitions between ``active``/``inactive`` freely (a scale
      taken out of service, not a lifecycle with a terminal state).
    """

    __slots__ = (
        "_asset_tag",
        "_certificate_expiry_date",
        "_certificate_ref",
        "_least_count_grams",
        "_make",
        "_model",
        "_status",
        "_tenant_id",
        "_warehouse_id",
    )

    def __init__(
        self,
        *,
        scale_id: uuid.UUID,
        tenant_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        asset_tag: str,
        least_count_grams: int,
        certificate_ref: str,
        certificate_expiry_date: date,
        make: str | None = None,
        model: str | None = None,
        status: str = "active",
        version: int = 1,
    ) -> None:
        super().__init__(scale_id, version=version)

        self._validate_least_count(least_count_grams)
        self._validate_asset_tag(asset_tag)
        if status not in SCALE_STATUSES:
            msg = f"Unknown scale status: '{status}'."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._warehouse_id = warehouse_id
        self._asset_tag = asset_tag
        self._least_count_grams = least_count_grams
        self._certificate_ref = certificate_ref
        self._certificate_expiry_date = certificate_expiry_date
        self._make = make
        self._model = model
        self._status = status

        self.record_event(
            ScaleRegistered(
                scale_id=scale_id,
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                certificate_expiry_date=certificate_expiry_date,
            )
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def warehouse_id(self) -> uuid.UUID:
        return self._warehouse_id

    @property
    def asset_tag(self) -> str:
        return self._asset_tag

    @property
    def least_count_grams(self) -> int:
        return self._least_count_grams

    @property
    def certificate_ref(self) -> str:
        return self._certificate_ref

    @property
    def certificate_expiry_date(self) -> date:
        return self._certificate_expiry_date

    @property
    def make(self) -> str | None:
        return self._make

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def status(self) -> str:
        return self._status

    def is_expired(self, *, as_of: date | None = None) -> bool:
        reference = as_of or datetime.now(UTC).date()
        return self._certificate_expiry_date < reference

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def replace_certificate(self, *, certificate_ref: str, certificate_expiry_date: date) -> None:
        """A renewed calibration certificate supersedes the old one in place —
        same asset, new validity window."""
        self._certificate_ref = certificate_ref
        self._certificate_expiry_date = certificate_expiry_date

        self.record_event(
            ScaleCertificateReplaced(
                scale_id=self.id,
                warehouse_id=self._warehouse_id,
                certificate_expiry_date=certificate_expiry_date,
            )
        )

    def set_status(self, status: str) -> None:
        if status not in SCALE_STATUSES:
            msg = f"Unknown scale status: '{status}'."
            raise InvariantViolation(msg)
        if status == self._status:
            return
        self._status = status
        self.record_event(
            ScaleStatusChanged(scale_id=self.id, warehouse_id=self._warehouse_id, status=status)
        )

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_least_count(least_count_grams: int) -> None:
        if least_count_grams <= 0:
            msg = "Scale least count must be a positive number of grams."
            raise InvariantViolation(msg)
        if least_count_grams > MAX_LEAST_COUNT_GRAMS:
            msg = (
                f"Scale least count of {least_count_grams} g exceeds the MDG-required "
                f"maximum of {MAX_LEAST_COUNT_GRAMS} g (MDG 2022 cl. 1.2(ii)(iii)) — "
                "this scale cannot be registered as MDG-compliant."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_asset_tag(asset_tag: str) -> None:
        if not asset_tag or not asset_tag.strip():
            msg = "Scale asset tag must not be empty."
            raise InvariantViolation(msg)
