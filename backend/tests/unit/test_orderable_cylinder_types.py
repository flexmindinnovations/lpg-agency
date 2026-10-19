"""`OrderableCylinderTypes`: what the booking forms list, and the guard that
refuses a booking the forms would have hidden."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from lpg.application.common.errors import CylinderNotOrderableError
from lpg.application.order.orderable import OrderableCylinderTypes
from lpg.domain.tenant.cylinder_type import CylinderType
from lpg.domain.tenant.price_list import PriceListEntry

TENANT_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()


@dataclass
class FakeCylinderTypes:
    types: list[CylinderType]

    async def get(self, cylinder_type_id: uuid.UUID) -> CylinderType | None:
        return next((t for t in self.types if t.id == cylinder_type_id), None)

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[CylinderType]:  # noqa: ARG002
        return self.types


@dataclass
class FakePriceLists:
    entries: list[PriceListEntry]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PriceListEntry]:  # noqa: ARG002
        return self.entries


@dataclass
class FakeStock:
    available: dict[uuid.UUID, int]
    excluded: list[uuid.UUID | None] = field(default_factory=list)

    async def available_filled_by_cylinder_type(
        self, branch_id: uuid.UUID, *, exclude_order_id: uuid.UUID | None = None
    ) -> dict[uuid.UUID, int]:
        assert branch_id == BRANCH_ID
        self.excluded.append(exclude_order_id)
        return self.available


def _type(name: str, *, active: bool = True) -> CylinderType:
    return CylinderType(uuid.uuid4(), TENANT_ID, name, Decimal("14.2"), is_active=active)


def _price(
    cylinder_type: CylinderType,
    amount: str,
    customer_type: str = "domestic",
    *,
    branch_id: uuid.UUID | None = None,
) -> PriceListEntry:
    return PriceListEntry(
        uuid.uuid4(),
        TENANT_ID,
        cylinder_type.id,
        customer_type,
        Decimal(amount),
        datetime.now(UTC) - timedelta(days=1),
        branch_id=branch_id,
    )


@dataclass
class Catalog:
    domestic: CylinderType = field(default_factory=lambda: _type("Domestic 14.2kg"))
    commercial: CylinderType = field(default_factory=lambda: _type("Commercial 19kg"))
    retired: CylinderType = field(default_factory=lambda: _type("Old 5kg", active=False))
    future: CylinderType = field(default_factory=lambda: _type("Industrial 47.5kg"))
    stock: FakeStock = field(default_factory=lambda: FakeStock({}))

    def service(self) -> OrderableCylinderTypes:
        future_price = PriceListEntry(
            uuid.uuid4(),
            TENANT_ID,
            self.future.id,
            "domestic",
            Decimal("4000"),
            datetime.now(UTC) + timedelta(days=5),
        )
        prices = [
            _price(self.domestic, "903"),
            _price(self.domestic, "880", branch_id=BRANCH_ID),
            _price(self.commercial, "1700", "commercial"),
            _price(self.retired, "400"),
            future_price,
        ]
        types = [self.domestic, self.commercial, self.retired, self.future]
        return OrderableCylinderTypes(
            FakeCylinderTypes(types),  # type: ignore[arg-type]
            FakePriceLists(prices),  # type: ignore[arg-type]
            self.stock,
        )


@pytest.fixture
def catalog() -> Catalog:
    catalog = Catalog()
    catalog.stock.available.update(
        {
            catalog.domestic.id: 12,
            catalog.commercial.id: 5,
            catalog.retired.id: 9,
            catalog.future.id: 9,
        }
    )
    return catalog


async def test_lists_only_active_priced_in_stock_types(catalog: Catalog) -> None:
    options = await catalog.service().list(
        tenant_id=TENANT_ID, branch_id=BRANCH_ID, customer_type="domestic"
    )

    # Commercial has no domestic price, Old 5kg is inactive, Industrial's
    # price only takes effect next week.
    assert [o.name for o in options] == ["Domestic 14.2kg"]
    assert options[0].unit_price == Decimal("880")  # the branch override wins
    assert options[0].available_quantity == 12


async def test_price_is_per_customer_type(catalog: Catalog) -> None:
    options = await catalog.service().list(
        tenant_id=TENANT_ID, branch_id=BRANCH_ID, customer_type="commercial"
    )

    assert [o.name for o in options] == ["Commercial 19kg"]


async def test_out_of_stock_or_overbooked_types_are_hidden(catalog: Catalog) -> None:
    catalog.stock.available[catalog.domestic.id] = 0
    assert (
        await catalog.service().list(
            tenant_id=TENANT_ID, branch_id=BRANCH_ID, customer_type="domestic"
        )
        == []
    )

    catalog.stock.available[catalog.domestic.id] = -3
    assert (
        await catalog.service().list(
            tenant_id=TENANT_ID, branch_id=BRANCH_ID, customer_type="domestic"
        )
        == []
    )


async def test_require_accepts_an_orderable_booking(catalog: Catalog) -> None:
    order_id = uuid.uuid4()
    await catalog.service().require(
        tenant_id=TENANT_ID,
        branch_id=BRANCH_ID,
        customer_type="domestic",
        lines=[(catalog.domestic.id, 12)],
        exclude_order_id=order_id,
    )

    assert catalog.stock.excluded == [order_id]


@pytest.mark.parametrize(
    ("pick", "quantity", "customer_type", "reason", "fragment"),
    [
        ("retired", 1, "domestic", "inactive", "Old 5kg is not available"),
        ("commercial", 1, "domestic", "no_price", "no price set for domestic"),
        ("future", 1, "domestic", "no_price", "Industrial 47.5kg has no price"),
        ("domestic", 13, "domestic", "insufficient_stock", "Only 12 filled"),
    ],
)
async def test_require_names_the_cylinder_and_the_reason(
    catalog: Catalog, pick: str, quantity: int, customer_type: str, reason: str, fragment: str
) -> None:
    cylinder_type: CylinderType = getattr(catalog, pick)
    with pytest.raises(CylinderNotOrderableError) as exc_info:
        await catalog.service().require(
            tenant_id=TENANT_ID,
            branch_id=BRANCH_ID,
            customer_type=customer_type,
            lines=[(cylinder_type.id, quantity)],
        )

    assert fragment in exc_info.value.message
    assert exc_info.value.context["reason"] == reason


async def test_require_refuses_an_out_of_stock_type(catalog: Catalog) -> None:
    catalog.stock.available.pop(catalog.domestic.id)
    with pytest.raises(CylinderNotOrderableError) as exc_info:
        await catalog.service().require(
            tenant_id=TENANT_ID,
            branch_id=BRANCH_ID,
            customer_type="domestic",
            lines=[(catalog.domestic.id, 1)],
        )

    assert "out of stock" in exc_info.value.message
    assert exc_info.value.context["reason"] == "out_of_stock"


async def test_require_adds_up_lines_of_the_same_type(catalog: Catalog) -> None:
    with pytest.raises(CylinderNotOrderableError):
        await catalog.service().require(
            tenant_id=TENANT_ID,
            branch_id=BRANCH_ID,
            customer_type="domestic",
            lines=[(catalog.domestic.id, 7), (catalog.domestic.id, 6)],
        )


async def test_require_refuses_an_unknown_type(catalog: Catalog) -> None:
    with pytest.raises(CylinderNotOrderableError):
        await catalog.service().require(
            tenant_id=TENANT_ID,
            branch_id=BRANCH_ID,
            customer_type="domestic",
            lines=[(uuid.uuid4(), 1)],
        )
