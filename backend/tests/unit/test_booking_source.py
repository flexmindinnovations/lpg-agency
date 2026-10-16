"""Unit tests for `resolve_booking_source` — the server, not the client, decides
which channel an order came in through."""

from __future__ import annotations

import pytest

from lpg.application.common.errors import ValidationError
from lpg.application.order.booking_source import resolve_booking_source


class TestCustomerLogins:
    @pytest.mark.parametrize(
        "requested", [None, "mobile_app", "staff", "phone", "walk_in", "whatsapp", "api"]
    )
    def test_a_customer_is_always_the_customer_app(self, requested: str | None) -> None:
        assert resolve_booking_source("customer", requested) == "mobile_app"


class TestStaff:
    @pytest.mark.parametrize(
        "role", ["agency_admin", "manager", "dispatcher", "accountant", "warehouse_staff"]
    )
    def test_defaults_to_the_dashboard(self, role: str) -> None:
        assert resolve_booking_source(role, None) == "staff"

    @pytest.mark.parametrize("requested", ["staff", "phone", "walk_in", "whatsapp", "api"])
    def test_may_record_the_channel_the_customer_used(self, requested: str) -> None:
        assert resolve_booking_source("agency_admin", requested) == requested

    @pytest.mark.parametrize("role", ["agency_admin", "dispatcher", "driver"])
    def test_cannot_claim_the_customer_app(self, role: str) -> None:
        with pytest.raises(ValidationError, match="Customer App"):
            resolve_booking_source(role, "mobile_app")
