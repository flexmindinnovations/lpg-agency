"""The new-agency checklist's GST step: each cylinder carries its own rate."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from lpg.application.tenant.setup_progress import (
    GetSetupProgressQuery,
    GetSetupProgressUseCase,
)


def _cylinder(rate: str | None, *, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        is_active=is_active, gst_rate_percent=None if rate is None else Decimal(rate)
    )


async def _gst_done(cylinders: list[SimpleNamespace], *, agency_rate: bool = False) -> bool:
    nothing = AsyncMock()
    nothing.list_for_tenant.return_value = []
    cylinder_types = AsyncMock()
    cylinder_types.list_for_tenant.return_value = cylinders
    configuration = AsyncMock()

    async def configured(_tenant: uuid.UUID, key: str) -> list[object]:
        return [object()] if agency_rate and key == "gst_rate_percent" else []

    configuration.list_for_tenant_and_key.side_effect = configured
    vehicles_and_drivers = AsyncMock()
    vehicles_and_drivers.count_drivers.return_value = 0
    vehicles_and_drivers.count_vehicles.return_value = 0
    use_case = GetSetupProgressUseCase(
        branches=nothing,
        warehouses=nothing,
        cylinder_types=cylinder_types,
        prices=nothing,
        configuration=configuration,
        staff=nothing,
        drivers=vehicles_and_drivers,
        vehicles=vehicles_and_drivers,
    )
    progress = await use_case.execute(GetSetupProgressQuery(uuid.uuid4()))
    return progress.done["gst"]


@pytest.mark.parametrize(
    ("cylinders", "done"),
    [
        ([], False),
        ([_cylinder("5"), _cylinder("18")], True),
        ([_cylinder("5"), _cylinder(None)], False),
        # A cylinder that is switched off is not sold, so it needs no rate.
        ([_cylinder("5"), _cylinder(None, is_active=False)], True),
        ([_cylinder("0")], True),
    ],
)
async def test_gst_is_done_when_every_cylinder_sold_has_a_rate(
    cylinders: list[SimpleNamespace], done: bool
) -> None:
    assert await _gst_done(cylinders) is done


async def test_the_older_agency_wide_rate_still_counts() -> None:
    assert await _gst_done([_cylinder(None)], agency_rate=True) is True
