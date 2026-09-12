"""OMC rate ingestion — AI Operational Intelligence, Horizon 1 Stage 3.

`OmcRateSourcePort` is the seam between "a monthly cron proposes price
changes for staff to review" (real, working, built in this stage) and
"where those rates actually come from" (not solved yet — see
`infrastructure/pricing/omc_scraper.py`'s module docstring for what was
tried and why). A second, genuinely working source is one new adapter class
implementing this Protocol plus one new branch in
`infrastructure/pricing/factory.py` — nothing above this layer changes,
the same swappable-adapter shape `application/ai/ports.ModelGatewayPort`
already proves for the model gateway (ADR-045).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OmcRate:
    """One OMC-published price point for one cylinder weight x customer
    type, as of `fetched_at`. `weight_kg` is nominal (e.g. `14.2`, `19.0`)
    — OMCs publish by cylinder weight, not by this codebase's per-tenant
    `cylinder_type` ids, so the caller maps it onto the tenant's own
    catalog by nearest weight match (`infrastructure/jobs/pricing_jobs.py`).
    """

    weight_kg: Decimal
    #: One of `domain.tenant.price_list.CUSTOMER_TYPES`.
    customer_type: str
    price: Decimal
    source_url: str
    fetched_at: datetime


@runtime_checkable
class OmcRateSourcePort(Protocol):
    async def fetch_rates(self, *, city: str, omc: str) -> list[OmcRate]:
        """Every rate this source has for `city`/`omc` right now.

        Returns an empty list — never raises — when nothing could be
        fetched. That covers both "this source genuinely has no data for
        this city/omc" and "the fetch failed" identically on purpose: the
        caller (the monthly cron) treats an empty result as "nothing to
        propose this run", and a real hard failure is the adapter's own
        job to log with enough detail to diagnose — never a wrong
        auto-price reaching `tenant.price_list_proposal` instead.
        """
        ...
