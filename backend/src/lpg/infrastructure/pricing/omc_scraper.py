"""OMC rate source adapters — AI Operational Intelligence, Horizon 1 Stage 3.

**No adapter here fetches live rates yet — this is documented, not
hidden.** Real research during this stage (2026-09-12) checked every
realistic public OMC/government price page for a plain-HTTP-client-
scrapeable source:

- `ppac.gov.in` (the government's own petroleum price aggregator) has no
  LPG price data of its own — its "RSP of Domestic LPG" link redirects
  straight to `iocl.com`.
- `iocl.com/prices-of-petroleum-products` has exactly the data needed
  (Indane 14.2kg domestic + 19kg commercial prices by metro, in clean
  HTML tables) — but the domain sits behind Sucuri's bot-protection
  layer, which requires executing a JS challenge to obtain a cookie
  before the real page loads. Confirmed live: a plain `httpx` GET returns
  the challenge stub (a `<script>` that sets a cookie and reloads), never
  the price table.
- `hindustanpetroleum.com/hp-price-list` returns 200 with a client-
  rendered JS shell — no price data anywhere in the static HTML.
- `bharatpetroleum.in` returns an error page despite a 200 status.

Defeating Sucuri would need a headless browser (Playwright) running
inside a scheduled backend job — a much heavier dependency than this
codebase carries anywhere else, slower and more fragile than every other
cron here, and arguably adversarial scraping of a protected site. Decided
against for this stage (see the ADR).

`NullOmcRateSource` is the honest placeholder this decision leads to: it
always returns no rates and logs why, so `fetch_omc_rates`
(`infrastructure/jobs/pricing_jobs.py`) is a real, working no-op today —
not a silently-broken implementation pretending to succeed. Everything
built around this port (the `tenant.price_list_proposal` review queue,
the cron scaffold, the admin accept/reject UI) is already useful on its
own; wiring in a genuinely working source later — a real scraper behind a
headless browser, or a tenant's own OMC dealer-portal API — is exactly
one new class here plus one new branch in
`infrastructure/pricing/factory.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.pricing.ports import OmcRate

_logger = get_logger(__name__)


class NullOmcRateSource:
    """Implements `OmcRateSourcePort`. Always returns `[]` — see module
    docstring for why no working adapter exists yet."""

    async def fetch_rates(self, *, city: str, omc: str) -> list[OmcRate]:
        _logger.warning(
            "omc_rate_source_not_configured",
            city=city,
            omc=omc,
            reason=(
                "no working OmcRateSourcePort adapter exists yet — "
                "see infrastructure/pricing/omc_scraper.py's module docstring"
            ),
        )
        return []
