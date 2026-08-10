"""`PriceListEntry`/`EffectivePriceResolver` — no database required."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.price_list import EffectivePriceResolver, PriceListEntry

_TENANT_ID = uuid.uuid4()
_CYLINDER_TYPE_ID = uuid.uuid4()
_BRANCH_ID = uuid.uuid4()


def _entry(
    price: str,
    effective_from: datetime,
    *,
    branch_id: uuid.UUID | None = None,
    customer_type: str = "domestic",
) -> PriceListEntry:
    return PriceListEntry(
        uuid.uuid4(),
        _TENANT_ID,
        _CYLINDER_TYPE_ID,
        customer_type,
        Decimal(price),
        effective_from,
        branch_id=branch_id,
    )


class TestConstruction:
    def test_rejects_an_unrecognized_customer_type(self) -> None:
        with pytest.raises(InvariantViolation):
            PriceListEntry(
                uuid.uuid4(),
                _TENANT_ID,
                _CYLINDER_TYPE_ID,
                "wholesale",
                Decimal("900.00"),
                datetime.now(UTC),
            )

    def test_rejects_a_non_positive_price(self) -> None:
        with pytest.raises(InvariantViolation):
            PriceListEntry(
                uuid.uuid4(),
                _TENANT_ID,
                _CYLINDER_TYPE_ID,
                "domestic",
                Decimal("0"),
                datetime.now(UTC),
            )

    def test_no_branch_id_means_tenant_wide_default(self) -> None:
        entry = _entry("900.00", datetime.now(UTC))

        assert entry.is_tenant_wide_default is True

    def test_a_branch_id_means_not_a_tenant_wide_default(self) -> None:
        entry = _entry("900.00", datetime.now(UTC), branch_id=_BRANCH_ID)

        assert entry.is_tenant_wide_default is False


class TestResolver:
    def test_returns_none_when_nothing_matches(self) -> None:
        result = EffectivePriceResolver.resolve(
            [],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=None,
            at=datetime.now(UTC),
        )

        assert result is None

    def test_falls_back_to_the_tenant_wide_default_when_no_branch_override_exists(self) -> None:
        now = datetime.now(UTC)
        default = _entry("900.00", now - timedelta(days=1))

        result = EffectivePriceResolver.resolve(
            [default],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=_BRANCH_ID,
            at=now,
        )

        assert result is default

    def test_a_branch_specific_override_wins_over_the_tenant_wide_default(self) -> None:
        now = datetime.now(UTC)
        default = _entry("900.00", now - timedelta(days=10))
        override = _entry("850.00", now - timedelta(days=1), branch_id=_BRANCH_ID)

        result = EffectivePriceResolver.resolve(
            [default, override],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=_BRANCH_ID,
            at=now,
        )

        assert result is override

    def test_a_different_branchs_override_does_not_apply(self) -> None:
        now = datetime.now(UTC)
        other_branch = uuid.uuid4()
        default = _entry("900.00", now - timedelta(days=10))
        other_override = _entry("850.00", now - timedelta(days=1), branch_id=other_branch)

        result = EffectivePriceResolver.resolve(
            [default, other_override],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=_BRANCH_ID,
            at=now,
        )

        assert result is default

    def test_ignores_entries_for_a_different_customer_type(self) -> None:
        now = datetime.now(UTC)
        commercial = _entry("1200.00", now - timedelta(days=1), customer_type="commercial")

        result = EffectivePriceResolver.resolve(
            [commercial],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=None,
            at=now,
        )

        assert result is None

    def test_picks_the_most_recent_applicable_default(self) -> None:
        now = datetime.now(UTC)
        older = _entry("900.00", now - timedelta(days=30))
        newer = _entry("950.00", now - timedelta(days=1))

        result = EffectivePriceResolver.resolve(
            [older, newer],
            cylinder_type_id=_CYLINDER_TYPE_ID,
            customer_type="domestic",
            branch_id=None,
            at=now,
        )

        assert result is newer
