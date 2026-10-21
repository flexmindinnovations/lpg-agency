"""`normalize_phone_number` — mobile sign-in accepts numbers without `+91`."""

from __future__ import annotations

import pytest

from lpg.api.v1.schemas.identity import OtpRequestRequest, OtpVerifyRequest
from lpg.domain.common.phone import normalize_phone_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9876543210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+919876543210", "+919876543210"),
        (" +91 98765-43210 ", "+919876543210"),
        ("(098765) 43210", "+919876543210"),
        ("+14155552671", "+14155552671"),
        ("12345", "12345"),
        ("abc", "abc"),
    ],
)
def test_normalize_phone_number(raw: str, expected: str) -> None:
    assert normalize_phone_number(raw) == expected


def test_otp_request_bodies_normalize_phone_number() -> None:
    request = OtpRequestRequest(tenant_id="dev-tenant", phone_number="9876543210")
    verify = OtpVerifyRequest(tenant_id="dev-tenant", phone_number="09876543210", code="123456")

    assert request.phone_number == "+919876543210"
    assert verify.phone_number == "+919876543210"
