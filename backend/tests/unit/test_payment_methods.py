"""The ways of paying an agency offers follow its own payment set-up."""

from __future__ import annotations

from lpg.application.accounting.payment_methods import offered_methods


def _codes(options: tuple[object, ...]) -> list[str]:
    return [o.code for o in options]  # type: ignore[attr-defined]


def test_an_agency_with_nothing_set_up_offers_cash_only_at_the_door() -> None:
    offered = offered_methods(
        has_upi=False, has_bank_details=False, online_available=False, credit_enabled=False
    )
    assert _codes(offered.booking) == ["cash"]
    assert _codes(offered.delivery) == ["cash"]
    assert _codes(offered.office) == ["cash", "cheque"]


def test_upi_follows_the_upi_id() -> None:
    offered = offered_methods(
        has_upi=True, has_bank_details=False, online_available=False, credit_enabled=False
    )
    assert _codes(offered.booking) == ["cash", "upi"]
    assert _codes(offered.office) == ["cash", "upi", "cheque"]


def test_online_payment_follows_the_connected_gateway() -> None:
    offered = offered_methods(
        has_upi=False, has_bank_details=False, online_available=True, credit_enabled=False
    )
    assert _codes(offered.booking) == ["cash", "online_gateway"]
    assert "online_gateway" not in _codes(offered.office)


def test_bank_transfer_follows_the_bank_details() -> None:
    offered = offered_methods(
        has_upi=False, has_bank_details=True, online_available=False, credit_enabled=False
    )
    assert _codes(offered.office) == ["cash", "cheque", "bank_transfer"]


def test_credit_is_a_doorstep_choice_only_when_a_limit_is_configured() -> None:
    off = offered_methods(
        has_upi=True, has_bank_details=True, online_available=True, credit_enabled=False
    )
    on = offered_methods(
        has_upi=True, has_bank_details=True, online_available=True, credit_enabled=True
    )
    assert "credit" not in _codes(off.delivery)
    assert _codes(on.delivery) == ["cash", "upi", "online_gateway", "credit"]
    assert "credit" not in _codes(on.booking)


def test_card_is_never_offered() -> None:
    offered = offered_methods(
        has_upi=True, has_bank_details=True, online_available=True, credit_enabled=True
    )
    for group in (offered.booking, offered.delivery, offered.office):
        assert "card" not in _codes(group)
