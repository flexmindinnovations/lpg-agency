"""Unit tests for `_resolve_subscription_intent` — the RBAC gate that maps a
WebSocket client's subscription intent to a server-built Redis channel."""

from __future__ import annotations

from lpg.api.v1.routers.ws import _resolve_subscription_intent

_TENANT = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"
_ORDER = "33333333-3333-3333-3333-333333333333"


def _claims(*, scope: str = "", role: str = "manager") -> dict[str, object]:
    return {"tenant_id": _TENANT, "sub": _USER, "scope": scope, "role": role}


def test_orders_intent_requires_orders_read() -> None:
    assert (
        _resolve_subscription_intent("orders", _claims(scope="orders:read"))
        == f"tenant:{_TENANT}:orders"
    )
    assert _resolve_subscription_intent("orders", _claims(scope="")) is None


def test_notifications_intent_is_always_scoped_to_the_caller() -> None:
    assert (
        _resolve_subscription_intent("notifications", _claims())
        == f"tenant:{_TENANT}:user:{_USER}"
    )


def test_dashboard_intent_requires_reports_read() -> None:
    assert (
        _resolve_subscription_intent("dashboard", _claims(scope="reports:read"))
        == f"tenant:{_TENANT}:dashboard"
    )
    assert _resolve_subscription_intent("dashboard", _claims()) is None


def test_per_order_intent_allows_a_customer() -> None:
    assert (
        _resolve_subscription_intent(f"order:{_ORDER}", _claims(role="customer"))
        == f"tenant:{_TENANT}:order:{_ORDER}"
    )


def test_unknown_intent_is_denied() -> None:
    assert _resolve_subscription_intent("everything", _claims(scope="orders:read")) is None


def test_missing_tenant_or_user_is_denied() -> None:
    assert _resolve_subscription_intent("orders", {"scope": "orders:read"}) is None
