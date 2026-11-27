"""Cylinder types through the real ASGI stack: sizes come from the standard
list, and a type can be changed or deleted only while nothing refers to it
(ADR-079). Includes tenant isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.test_order_endpoints_smoke import (
    _seed_full_fixture_set,
    stack,  # noqa: F401 - re-exported fixture
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncEngine

    from tests.integration.test_order_endpoints_smoke import _AppAndClient, _Fixtures

pytestmark = pytest.mark.integration

TYPES = "/api/v1/admin/cylinder-types"


async def _agency(client: AsyncClient, engine: AsyncEngine) -> tuple[_Fixtures, dict[str, str]]:
    """An agency whose one older type, "14.2kg", already has a price and stock."""
    fixtures = await _seed_full_fixture_set(client, engine)
    return fixtures, {"Authorization": f"Bearer {fixtures.admin_token}"}


class TestStandardSizes:
    async def test_a_type_is_created_from_a_listed_size_once(
        self,
        stack: _AppAndClient,  # noqa: F811
        admin_engine: AsyncEngine,
    ) -> None:
        client = stack.client
        _, headers = await _agency(client, admin_engine)

        sizes = await client.get("/api/v1/admin/cylinder-sizes", headers=headers)
        created = await client.post(TYPES, json={"size_code": "commercial_19"}, headers=headers)
        again = await client.post(TYPES, json={"size_code": "commercial_19"}, headers=headers)
        unknown = await client.post(TYPES, json={"size_code": "commercial_12"}, headers=headers)
        typed = await client.post(TYPES, json={"name": "My 13kg", "weight_kg": 13}, headers=headers)

        assert len(sizes.json()) == 9
        assert created.status_code == 201, created.text
        assert created.json()["name"] == "19 kg Commercial"
        assert created.json()["size_code"] == "commercial_19"
        assert created.json()["category"] == "commercial"
        assert again.status_code == 409, again.text
        assert unknown.status_code == 422, unknown.text
        assert typed.status_code == 422, typed.text


class TestChangeAndDelete:
    async def test_an_unused_type_can_be_resized_and_deleted(
        self,
        stack: _AppAndClient,  # noqa: F811
        admin_engine: AsyncEngine,
    ) -> None:
        client = stack.client
        _, headers = await _agency(client, admin_engine)
        created = await client.post(TYPES, json={"size_code": "commercial_19"}, headers=headers)
        url = f"{TYPES}/{created.json()['id']}"

        usage = await client.get(f"{url}/usage", headers=headers)
        resized = await client.patch(
            url,
            json={"size_code": "commercial_35", "hsn_code": "27111900", "gst_rate_percent": "18"},
            headers=headers,
        )
        deleted = await client.delete(url, headers=headers)
        listed = await client.get(TYPES, headers=headers)
        gone = await client.get(f"{url}/usage", headers=headers)
        added_again = await client.post(TYPES, json={"size_code": "commercial_35"}, headers=headers)

        assert usage.json()["used_in"] == []
        assert len(usage.json()["allowed_size_codes"]) == 9
        assert resized.status_code == 200, resized.text
        assert resized.json()["name"] == "35 kg Commercial"
        assert resized.json()["gst_rate_percent"] is not None
        assert deleted.status_code == 204, deleted.text
        assert "35 kg Commercial" not in [t["name"] for t in listed.json()]
        assert gone.status_code == 404, gone.text
        assert added_again.status_code == 201, added_again.text

    async def test_a_used_type_cannot_be_deleted_or_change_weight(
        self,
        stack: _AppAndClient,  # noqa: F811
        admin_engine: AsyncEngine,
    ) -> None:
        client = stack.client
        fixtures, headers = await _agency(client, admin_engine)
        url = f"{TYPES}/{fixtures.cylinder_type_id}"

        usage = await client.get(f"{url}/usage", headers=headers)
        deleted = await client.delete(url, headers=headers)
        reweighed = await client.patch(url, json={"size_code": "commercial_19"}, headers=headers)
        # The older record may take the list size of the same weight.
        relabelled = await client.patch(url, json={"size_code": "domestic_14_2"}, headers=headers)
        after = await client.get(f"{url}/usage", headers=headers)

        assert {"stock records", "prices"} <= set(usage.json()["used_in"])
        assert usage.json()["allowed_size_codes"] == ["domestic_14_2"]
        assert deleted.status_code == 409, deleted.text
        assert "Deactivate it instead" in deleted.text
        assert reweighed.status_code == 409, reweighed.text
        assert relabelled.status_code == 200, relabelled.text
        assert relabelled.json()["name"] == "14.2 kg Domestic"
        assert after.json()["allowed_size_codes"] == ["domestic_14_2"]

    async def test_an_hsn_code_needs_a_rate(
        self,
        stack: _AppAndClient,  # noqa: F811
        admin_engine: AsyncEngine,
    ) -> None:
        client = stack.client
        fixtures, headers = await _agency(client, admin_engine)

        response = await client.patch(
            f"{TYPES}/{fixtures.cylinder_type_id}",
            json={"hsn_code": "27111900"},
            headers=headers,
        )

        assert response.status_code == 422, response.text

    async def test_another_agency_and_a_customer_cannot_touch_it(
        self,
        stack: _AppAndClient,  # noqa: F811
        admin_engine: AsyncEngine,
    ) -> None:
        client = stack.client
        fixtures, _ = await _agency(client, admin_engine)
        _, outsider = await _agency(client, admin_engine)
        customer = {"Authorization": f"Bearer {fixtures.customer_token}"}
        url = f"{TYPES}/{fixtures.cylinder_type_id}"

        for headers, expected in ((outsider, 404), (customer, 403)):
            usage = await client.get(f"{url}/usage", headers=headers)
            changed = await client.patch(url, json={"size_code": "domestic_14_2"}, headers=headers)
            deleted = await client.delete(url, headers=headers)

            assert [usage.status_code, changed.status_code, deleted.status_code] == [expected] * 3
