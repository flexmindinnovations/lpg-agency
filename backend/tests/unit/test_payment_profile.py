"""Payment profile validation and UPI link building (ADR-066)."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from lpg.application.accounting.payment_profile import PaymentProfile, build_upi_uri
from lpg.application.common.errors import ValidationError


def _full(**overrides: str) -> dict[str, str]:
    fields = {
        "account_holder": "Sai Gas Agency",
        "bank_name": "HDFC Bank",
        "account_number": "50100123456789",
        "ifsc": "hdfc0001234",
        "branch": "Pune",
        "upi_id": "SaiGas@okhdfcbank",
        "upi_payee_name": "",
        "invoice_footer_note": "",
    }
    fields.update(overrides)
    return fields


def test_normalises_and_defaults_payee_to_account_holder() -> None:
    profile = PaymentProfile.validated(**_full())
    assert profile.ifsc == "HDFC0001234"
    assert profile.upi_id == "saigas@okhdfcbank"
    assert profile.payee_name == "Sai Gas Agency"
    assert profile.has_bank_details
    assert profile.has_upi


def test_blank_profile_is_valid() -> None:
    profile = PaymentProfile.validated(**dict.fromkeys(_full(), ""))
    assert not profile.has_bank_details
    assert not profile.has_upi


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"ifsc": "HDFC123"}, "IFSC"),
        ({"account_number": "12AB"}, "9 to 18 digits"),
        ({"upi_id": "no-handle"}, "name@bank"),
        ({"account_holder": ""}, "together"),
    ],
)
def test_rejects_bad_values(override: dict[str, str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        PaymentProfile.validated(**_full(**override))


def test_upi_only_needs_a_payee_name() -> None:
    blank_bank = {
        "account_holder": "",
        "account_number": "",
        "ifsc": "",
        "bank_name": "",
        "branch": "",
    }
    with pytest.raises(ValidationError, match="payee name"):
        PaymentProfile.validated(**_full(**blank_bank))
    profile = PaymentProfile.validated(**_full(**blank_bank, upi_payee_name="Sai Gas"))
    assert profile.payee_name == "Sai Gas"


def test_upi_uri_carries_payee_amount_and_note() -> None:
    profile = PaymentProfile.validated(**_full())
    uri = build_upi_uri(
        profile, amount=Decimal("1234.5"), note="LPG ORD000027", reference="ORD000027"
    )
    parts = urlsplit(uri)
    query = parse_qs(parts.query)
    assert parts.scheme == "upi"
    assert query["pa"] == ["saigas@okhdfcbank"]
    assert query["pn"] == ["Sai Gas Agency"]
    assert query["am"] == ["1234.50"]
    assert query["cu"] == ["INR"]
    assert query["tn"] == ["LPG ORD000027"]
    assert query["tr"] == ["ORD000027"]
