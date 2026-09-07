"""Unit tests for the Scale aggregate (Weighment Part 1)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.compliance.scale import (
    MAX_LEAST_COUNT_GRAMS,
    Scale,
    ScaleCertificateReplaced,
    ScaleRegistered,
    ScaleStatusChanged,
)


def _scale(**overrides: object) -> Scale:
    kwargs: dict[str, object] = {
        "scale_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "warehouse_id": uuid.uuid4(),
        "asset_tag": "SCALE-001",
        "least_count_grams": 10,
        "certificate_ref": "tenant/x/compliance-staging/scale_cert.pdf",
        "certificate_expiry_date": date(2030, 1, 1),
    }
    kwargs.update(overrides)
    return Scale(**kwargs)  # type: ignore[arg-type]


class TestConstruction:
    def test_records_a_registered_event(self) -> None:
        scale = _scale()
        assert isinstance(scale.events[0], ScaleRegistered)
        assert scale.status == "active"

    def test_max_least_count_constant_is_ten_grams(self) -> None:
        # MDG 2022 cl. 1.2(ii)(iii) — pinned so a change to this constant is
        # a deliberate, reviewed act, not an accidental one.
        assert MAX_LEAST_COUNT_GRAMS == 10

    def test_rejects_a_least_count_above_the_mdg_maximum(self) -> None:
        with pytest.raises(InvariantViolation, match="exceeds the MDG-required maximum"):
            _scale(least_count_grams=11)

    def test_rejects_a_zero_or_negative_least_count(self) -> None:
        with pytest.raises(InvariantViolation, match="positive number of grams"):
            _scale(least_count_grams=0)

    def test_accepts_the_maximum_permitted_least_count(self) -> None:
        scale = _scale(least_count_grams=10)
        assert scale.least_count_grams == 10

    def test_rejects_an_empty_asset_tag(self) -> None:
        with pytest.raises(InvariantViolation, match="asset tag must not be empty"):
            _scale(asset_tag="  ")

    def test_rejects_an_unknown_status(self) -> None:
        with pytest.raises(InvariantViolation, match="Unknown scale status"):
            _scale(status="retired")


class TestExpiry:
    def test_is_expired_compares_against_a_reference_date(self) -> None:
        scale = _scale(certificate_expiry_date=date(2026, 6, 1))
        assert scale.is_expired(as_of=date(2026, 7, 1)) is True
        assert scale.is_expired(as_of=date(2026, 5, 1)) is False


class TestCommands:
    def test_replace_certificate_updates_ref_and_expiry_and_records_an_event(self) -> None:
        scale = _scale(certificate_expiry_date=date(2026, 1, 1))
        scale.replace_certificate(
            certificate_ref="tenant/x/compliance-staging/new_cert.pdf",
            certificate_expiry_date=date(2029, 1, 1),
        )
        assert scale.certificate_ref == "tenant/x/compliance-staging/new_cert.pdf"
        assert scale.certificate_expiry_date == date(2029, 1, 1)
        assert isinstance(scale.events[-1], ScaleCertificateReplaced)

    def test_set_status_records_an_event(self) -> None:
        scale = _scale()
        scale.set_status("inactive")
        assert scale.status == "inactive"
        assert isinstance(scale.events[-1], ScaleStatusChanged)

    def test_set_status_to_the_same_value_is_a_no_op(self) -> None:
        scale = _scale()
        events_before = len(scale.events)
        scale.set_status("active")
        assert len(scale.events) == events_before

    def test_set_status_rejects_an_unknown_value(self) -> None:
        scale = _scale()
        with pytest.raises(InvariantViolation, match="Unknown scale status"):
            scale.set_status("retired")
