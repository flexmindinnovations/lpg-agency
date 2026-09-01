"""Unit tests for the driver-ownership guard shared by the mixed-role
``orders:dispatch`` endpoints (``POST /orders/{id}/depart`` and
``.../reschedule``).

``orders:dispatch`` is granted to both dispatch staff and the ``driver``
role (``7c3f1a9e2b4d``). ``_require_own_driver_order_when_driver`` is a
no-op for staff and, for a ``driver`` principal, enforces the same
404-not-403 ownership rule the ``orders:deliver`` endpoints already apply.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.api.v1.routers.order import _require_own_driver_order_when_driver
from lpg.application.common.errors import NotFoundError
from lpg.application.delivery.ports import RouteStopOwner
from lpg.application.identity.principal import JwtAuthenticatedPrincipal


def _principal(role: str) -> JwtAuthenticatedPrincipal:
    return JwtAuthenticatedPrincipal(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        permission_codes=frozenset({"orders:dispatch"}),
    )


async def test_staff_principal_is_a_no_op() -> None:
    order_repo, driver_repo, route_repo = AsyncMock(), AsyncMock(), AsyncMock()

    await _require_own_driver_order_when_driver(
        uuid.uuid4(), _principal("dispatcher"), order_repo, driver_repo, route_repo
    )

    order_repo.get_by_id.assert_not_awaited()
    driver_repo.get_by_identity_user_id.assert_not_awaited()
    route_repo.get_stop_owner.assert_not_awaited()


async def test_driver_owning_the_order_passes() -> None:
    driver_id = uuid.uuid4()
    stop_id = uuid.uuid4()

    driver_repo = AsyncMock()
    driver_repo.get_by_identity_user_id.return_value = MagicMock(id=driver_id)
    order_repo = AsyncMock()
    order_repo.get_by_id.return_value = MagicMock(route_stop_id=stop_id)
    route_repo = AsyncMock()
    route_repo.get_stop_owner.return_value = RouteStopOwner(
        route_id=uuid.uuid4(), driver_id=driver_id, vehicle_id=uuid.uuid4()
    )

    await _require_own_driver_order_when_driver(
        uuid.uuid4(), _principal("driver"), order_repo, driver_repo, route_repo
    )


async def test_driver_not_owning_the_order_is_404() -> None:
    driver_repo = AsyncMock()
    driver_repo.get_by_identity_user_id.return_value = MagicMock(id=uuid.uuid4())
    order_repo = AsyncMock()
    order_repo.get_by_id.return_value = MagicMock(route_stop_id=uuid.uuid4())
    route_repo = AsyncMock()
    route_repo.get_stop_owner.return_value = RouteStopOwner(
        route_id=uuid.uuid4(), driver_id=uuid.uuid4(), vehicle_id=uuid.uuid4()
    )

    with pytest.raises(NotFoundError):
        await _require_own_driver_order_when_driver(
            uuid.uuid4(), _principal("driver"), order_repo, driver_repo, route_repo
        )


async def test_driver_order_with_no_route_stop_is_404() -> None:
    driver_repo = AsyncMock()
    driver_repo.get_by_identity_user_id.return_value = MagicMock(id=uuid.uuid4())
    order_repo = AsyncMock()
    order_repo.get_by_id.return_value = MagicMock(route_stop_id=None)
    route_repo = AsyncMock()

    with pytest.raises(NotFoundError):
        await _require_own_driver_order_when_driver(
            uuid.uuid4(), _principal("driver"), order_repo, driver_repo, route_repo
        )
    route_repo.get_stop_owner.assert_not_awaited()
