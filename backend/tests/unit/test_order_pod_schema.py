"""Unit tests for `ProofOfDeliverySubmission`'s `dac_code` format validation
(Delivery Authentication Code, Phase 20 subsystem 4) — format only (6
digits), never authenticity; this platform has no OMC portal API to check a
DAC against."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from lpg.api.v1.schemas.order import ProofOfDeliverySubmission


def _submission(**overrides: object) -> ProofOfDeliverySubmission:
    kwargs: dict[str, object] = {
        "signature_blob_ref": "tenant/x/pod/sig.png",
        "photo_blob_ref": "tenant/x/pod/photo.jpg",
        "gps_lat": Decimal("12.9716"),
        "gps_lng": Decimal("77.5946"),
        "payment_method": "cash",
        "amount_collected": Decimal("100"),
    }
    kwargs.update(overrides)
    return ProofOfDeliverySubmission(**kwargs)


class TestDacCodeFormat:
    def test_a_valid_six_digit_code_is_accepted(self) -> None:
        submission = _submission(dac_code="123456")
        assert submission.dac_code == "123456"

    def test_omitting_dac_code_defaults_to_none(self) -> None:
        submission = _submission()
        assert submission.dac_code is None

    def test_explicit_none_is_accepted(self) -> None:
        submission = _submission(dac_code=None)
        assert submission.dac_code is None

    @pytest.mark.parametrize(
        "bad_value",
        [
            "12345",  # too short
            "1234567",  # too long
            "abcdef",  # non-numeric
            "12345a",  # mixed
            " 123456",  # leading whitespace
        ],
    )
    def test_a_malformed_code_is_rejected(self, bad_value: str) -> None:
        with pytest.raises(ValidationError):
            _submission(dac_code=bad_value)
