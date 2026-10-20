"""How an invoice line's GST is decided (BR-16, BR-31, DA-06).

The rate comes from the cylinder type being sold — domestic and commercial
LPG are taxed differently, so one tenant-wide rate cannot be right for
both. A tenant that only ever set the older tenant-wide `gst_rate_percent`
keeps getting that rate for cylinder types it has not classified yet.
When neither exists, invoicing stops with `GstNotConfiguredError` instead
of issuing a 0% tax invoice: an under-taxed invoice is a filing problem for
the agency, while a held invoice is fixed by configuring the rate and
issuing it from the Invoices screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from lpg.application.common.errors import ValidationError
from lpg.config.logging import get_logger
from lpg.domain.accounting.invoice import PlaceOfSupply
from lpg.domain.common.gst import state_code_for
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable
    from datetime import datetime

    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        TenantConfigurationRepository,
        TenantRepository,
    )
    from lpg.domain.customer.customer import Customer

_logger = get_logger(__name__)

_LEGACY_TENANT_RATE_KEY = "gst_rate_percent"


class GstNotConfiguredError(ValidationError):
    """No GST rate is configured for something being invoiced."""

    error_code = "GST_NOT_CONFIGURED"
    title = "GST is not configured"


@dataclass(frozen=True, slots=True)
class GstClass:
    """The GST treatment of one cylinder type at a point in time."""

    hsn_code: str | None
    rate_percent: Decimal


async def _legacy_tenant_rate(
    tenant_config_repository: TenantConfigurationRepository,
    tenant_id: uuid.UUID,
    at: datetime,
) -> Decimal | None:
    configs = await tenant_config_repository.list_for_tenant_and_key(
        tenant_id, _LEGACY_TENANT_RATE_KEY
    )
    resolved = TenantConfigurationResolver.resolve(configs, _LEGACY_TENANT_RATE_KEY, at)
    raw = resolved.config_value if resolved else None
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        # A malformed value is "not configured", never "0%".
        _logger.warning("invalid_gst_rate", gst_rate=str(raw), tenant_id=str(tenant_id))
        return None


async def resolve_gst_classes(
    *,
    cylinder_type_repository: CylinderTypeRepository,
    tenant_config_repository: TenantConfigurationRepository,
    tenant_id: uuid.UUID,
    cylinder_type_ids: Iterable[uuid.UUID],
    at: datetime,
) -> dict[uuid.UUID, GstClass]:
    """The GST class of every cylinder type given, or `GstNotConfiguredError`
    naming the ones without a rate.
    """
    classes: dict[uuid.UUID, GstClass] = {}
    unconfigured: list[str] = []
    legacy_rate: Decimal | None = None
    legacy_loaded = False
    for cylinder_type_id in dict.fromkeys(cylinder_type_ids):
        cylinder_type = await cylinder_type_repository.get(cylinder_type_id)
        if cylinder_type is not None and cylinder_type.gst_rate_percent is not None:
            classes[cylinder_type_id] = GstClass(
                hsn_code=cylinder_type.hsn_code, rate_percent=cylinder_type.gst_rate_percent
            )
            continue
        if not legacy_loaded:
            legacy_rate = await _legacy_tenant_rate(tenant_config_repository, tenant_id, at)
            legacy_loaded = True
        if legacy_rate is not None:
            classes[cylinder_type_id] = GstClass(
                hsn_code=cylinder_type.hsn_code if cylinder_type else None,
                rate_percent=legacy_rate,
            )
            continue
        unconfigured.append(cylinder_type.name if cylinder_type else str(cylinder_type_id))

    if unconfigured:
        names = ", ".join(unconfigured)
        msg = (
            f"GST is not set up for {names}. Set the HSN code and GST rate in "
            "Admin > Cylinder Types, then issue the invoice from the Invoices page."
        )
        raise GstNotConfiguredError(msg, cylinder_types=unconfigured)
    return classes


def _primary_address_state(customer: Customer) -> str | None:
    addresses = list(customer.addresses)
    address = next((a for a in addresses if a.is_primary), None) or next(iter(addresses), None)
    return address.state if address is not None else None


def customer_gstin(customer: Customer | None) -> str | None:
    """The customer's GSTIN when they are a registered business (B2B).

    Read defensively: the GSTIN field is added to `Customer` by the
    customer-onboarding work (DO-02); until then every customer is B2C.
    """
    value = getattr(customer, "gstin", None) if customer is not None else None
    return value.strip().upper() if isinstance(value, str) and value.strip() else None


async def resolve_place_of_supply(
    *,
    tenant_repository: TenantRepository,
    tenant_id: uuid.UUID,
    customer: Customer | None,
) -> PlaceOfSupply:
    """Supplier state from the agency profile; place of supply from the
    customer's GSTIN (B2B), else their address state, else the agency's own
    state — a doorstep LPG delivery is almost always intra-state.
    """
    tenant = await tenant_repository.get(tenant_id)
    profile = tenant.business_profile if tenant is not None else None
    supplier_state = profile.state_code if profile is not None else None
    gstin = customer_gstin(customer)
    destination = (
        gstin[:2]
        if gstin
        else (state_code_for(_primary_address_state(customer)) if customer else None)
    )
    return PlaceOfSupply(
        supplier_state_code=supplier_state,
        place_of_supply_state_code=destination or supplier_state,
        customer_gstin=gstin,
    )
