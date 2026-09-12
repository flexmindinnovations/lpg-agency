"""Unit tests for `PriceListProposal` (domain) and the OMC-rate mapping
helpers (AI Operational Intelligence, Horizon 1 Stage 3). No DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from lpg.application.pricing.ports import OmcRate
from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.cylinder_type import CylinderType
from lpg.domain.tenant.price_list_proposal import PriceListProposal
from lpg.infrastructure.jobs.pricing_jobs import _first_of_next_month, _match_cylinder_type


def _proposal(*, status: str = "pending") -> PriceListProposal:
    return PriceListProposal(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "domestic",
        Decimal("950.00"),
        datetime(2026, 10, 1, tzinfo=UTC),
        "https://example.com/rates",
        datetime(2026, 9, 12, tzinfo=UTC),
        status=status,
    )


def test_rejects_a_non_positive_price() -> None:
    with pytest.raises(InvariantViolation):
        PriceListProposal(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            "domestic",
            Decimal("0.00"),
            datetime(2026, 10, 1, tzinfo=UTC),
            "https://example.com/rates",
            datetime(2026, 9, 12, tzinfo=UTC),
        )


def test_rejects_an_unrecognized_customer_type() -> None:
    with pytest.raises(InvariantViolation):
        PriceListProposal(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            "wholesale",
            Decimal("950.00"),
            datetime(2026, 10, 1, tzinfo=UTC),
            "https://example.com/rates",
            datetime(2026, 9, 12, tzinfo=UTC),
        )


def test_accept_marks_accepted_and_stamps_reviewer() -> None:
    proposal = _proposal()
    reviewer = uuid.uuid4()

    proposal.accept(reviewed_by=reviewer)

    assert proposal.status == "accepted"
    assert proposal.reviewed_by == reviewer
    assert proposal.reviewed_at is not None


def test_reject_marks_rejected_and_stamps_reviewer() -> None:
    proposal = _proposal()
    reviewer = uuid.uuid4()

    proposal.reject(reviewed_by=reviewer)

    assert proposal.status == "rejected"
    assert proposal.reviewed_by == reviewer


def test_cannot_accept_a_non_pending_proposal() -> None:
    proposal = _proposal(status="accepted")
    with pytest.raises(InvariantViolation):
        proposal.accept(reviewed_by=uuid.uuid4())


def test_cannot_reject_a_non_pending_proposal() -> None:
    proposal = _proposal(status="rejected")
    with pytest.raises(InvariantViolation):
        proposal.reject(reviewed_by=uuid.uuid4())


# --- _first_of_next_month --------------------------------------------------


def test_first_of_next_month_within_a_year() -> None:
    assert _first_of_next_month(date(2026, 9, 12)) == date(2026, 10, 1)


def test_first_of_next_month_rolls_over_the_year() -> None:
    assert _first_of_next_month(date(2026, 12, 15)) == date(2027, 1, 1)


# --- _match_cylinder_type ---------------------------------------------------


def _cylinder_type(weight_kg: str) -> CylinderType:
    return CylinderType(uuid.uuid4(), uuid.uuid4(), f"{weight_kg}kg", Decimal(weight_kg))


def _rate(weight_kg: str, customer_type: str = "domestic") -> OmcRate:
    return OmcRate(
        weight_kg=Decimal(weight_kg),
        customer_type=customer_type,
        price=Decimal("950.00"),
        source_url="https://example.com/rates",
        fetched_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def test_matches_the_nearest_cylinder_type_within_tolerance() -> None:
    catalog = [_cylinder_type("14.20"), _cylinder_type("19.00"), _cylinder_type("47.50")]
    matched = _match_cylinder_type(_rate("14.2"), catalog)
    assert matched is not None
    assert matched.weight_kg == Decimal("14.20")


def test_no_match_when_nothing_is_within_tolerance() -> None:
    catalog = [_cylinder_type("19.00"), _cylinder_type("47.50")]
    assert _match_cylinder_type(_rate("14.2"), catalog) is None


def test_no_match_against_an_empty_catalog() -> None:
    assert _match_cylinder_type(_rate("14.2"), []) is None
