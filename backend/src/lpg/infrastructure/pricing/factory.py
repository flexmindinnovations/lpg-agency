"""Picks the `OmcRateSourcePort` adapter from `Settings.omc_rate_provider`.

Same shape as `infrastructure/ai/factory.py` picking the model gateway
(ADR-045): one function, one branch per adapter. An unrecognized
`omc_rate_provider` value raises at first use, not a silent fallback —
fail-loud-on-misconfiguration, matching this codebase's convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.pricing.ports import OmcRateSourcePort
    from lpg.config.settings import Settings


def get_omc_rate_source(settings: Settings) -> OmcRateSourcePort:
    if settings.omc_rate_provider == "none":
        from lpg.infrastructure.pricing.omc_scraper import NullOmcRateSource

        return NullOmcRateSource()
    msg = (
        f"Unknown omc_rate_provider '{settings.omc_rate_provider}'. "
        "Only 'none' (the documented placeholder — see omc_scraper.py) is "
        "implemented; add a new adapter class and a branch here once a "
        "working rate source exists."
    )
    raise ValueError(msg)
