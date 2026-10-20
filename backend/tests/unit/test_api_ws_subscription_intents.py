"""Unit tests for `_resolve_subscription_intent` — the RBAC gate that maps a
WebSocket client's subscription intent to a server-built Redis channel."""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.routers.ws import _resolve_subscription_intent

_TENANT = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"
_ORDER = "33333333-3333-3333-3333-333333333333"
_DRIVER = uuid.UUID("44444444-4444-4444-4444-444444444444")


class _FakeOwnership:
    def __init__(self, *, owned_orders: set[str] | None = None) -> None:
        self._owned = owned_orders or set()

    async def driver_id_for(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID | None:
        return _DRIVER if str(user_id) == _USER else None

    async def customer_owns_order(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool:
        return str(order_id) in self._owned


def _claims(*, scope: str = "", role: str = "manager") -> dict[str, object]:
    return {"tenant_id": _TENANT, "sub": _USER, "scope": scope, "role": role}


pytestmark = pytest.mark.asyncio


async def test_orders_intent_requires_orders_read() -> None:
    assert (
        await _resolve_subscription_intent("orders", _claims(scope="orders:read"))
        == f"tenant:{_TENANT}:orders"
    )
    assert await _resolve_subscription_intent("orders", _claims(scope="")) is None


@pytest.mark.parametrize("role", ["customer", "driver"])
async def test_tenant_wide_feeds_are_staff_only(role: str) -> None:
    # Customers and drivers hold `orders:read` for their own orders; that
    # must not open the whole tenant's order and dispatch feeds.
    claims = _claims(scope="orders:read routes:read reports:read", role=role)
    for intent in ("orders", "dispatch", "dashboard"):
        assert await _resolve_subscription_intent(intent, claims) is None


async def test_notifications_intent_is_always_scoped_to_the_caller() -> None:
    assert (
        await _resolve_subscription_intent("notifications", _claims())
        == f"tenant:{_TENANT}:user:{_USER}"
    )


async def test_dashboard_intent_requires_reports_read() -> None:
    assert (
        await _resolve_subscription_intent("dashboard", _claims(scope="reports:read"))
        == f"tenant:{_TENANT}:dashboard"
    )
    assert await _resolve_subscription_intent("dashboard", _claims()) is None


async def test_per_order_intent_allows_a_customer_only_for_their_own_order() -> None:
    owner = _FakeOwnership(owned_orders={_ORDER})
    claims = _claims(role="customer", scope="orders:read")
    assert (
        await _resolve_subscription_intent(f"order:{_ORDER}", claims, owner)
        == f"tenant:{_TENANT}:order:{_ORDER}"
    )
    other = str(uuid.uuid4())
    assert await _resolve_subscription_intent(f"order:{other}", claims, owner) is None
    # No ownership lookup available: fail closed.
    assert await _resolve_subscription_intent(f"order:{_ORDER}", claims) is None


async def test_per_order_intent_allows_staff_with_orders_read() -> None:
    assert (
        await _resolve_subscription_intent(f"order:{_ORDER}", _claims(scope="orders:read"))
        == f"tenant:{_TENANT}:order:{_ORDER}"
    )
    assert await _resolve_subscription_intent("order:not-a-uuid", _claims()) is None


async def test_driver_intent_uses_the_driver_record_not_the_login() -> None:
    # Route events publish to `driver:{Driver.id}`; the login id never matched.
    channel = await _resolve_subscription_intent("driver", _claims(role="driver"), _FakeOwnership())
    assert channel == f"tenant:{_TENANT}:driver:{_DRIVER}"
    assert await _resolve_subscription_intent("driver", _claims(), _FakeOwnership()) is None


async def test_unknown_intent_is_denied() -> None:
    assert await _resolve_subscription_intent("everything", _claims(scope="orders:read")) is None


async def test_missing_tenant_or_user_is_denied() -> None:
    assert await _resolve_subscription_intent("orders", {"scope": "orders:read"}) is None
