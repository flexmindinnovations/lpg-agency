"""IFSC and UPI checks on the agency's payment details (ADR-066)."""

from __future__ import annotations

import httpx
import pytest

from lpg.application.accounting.payment_profile import PaymentProfile
from lpg.application.accounting.payment_verification import (
    IfscDetails,
    IfscLookupUnavailableError,
    check_ifsc,
    check_upi_id,
)
from lpg.application.common.errors import ValidationError
from lpg.infrastructure.payments.ifsc_directory import RazorpayIfscDirectory

_HDFC = {
    "IFSC": "HDFC0001234",
    "BANK": "HDFC Bank",
    "BRANCH": "PARK STREET",
    "CITY": "JAIPUR",
    "STATE": "RAJASTHAN",
    "ADDRESS": "3 PARK STREET",
    "UPI": True,
    "NEFT": True,
    "IMPS": True,
}


class _Directory:
    def __init__(self, answer: IfscDetails | Exception | None) -> None:
        self._answer = answer

    async def lookup(self, ifsc: str) -> IfscDetails | None:  # noqa: ARG002
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _directory(handler: httpx.MockTransport) -> RazorpayIfscDirectory:
    return RazorpayIfscDirectory(base_url="https://ifsc.test", transport=handler)


def test_known_handle_names_its_provider() -> None:
    check = check_upi_id("saigas@okhdfcbank")
    assert check.handle_known
    assert check.provider == "Google Pay (HDFC Bank)"


def test_unknown_handle_is_reported_not_rejected() -> None:
    check = check_upi_id("saigas@newbank")
    assert check.format_valid
    assert not check.handle_known
    assert check.provider is None


async def test_ifsc_statuses() -> None:
    details = IfscDetails(
        "HDFC0001234", "HDFC Bank", "Park Street", "Jaipur", "RJ", "", True, True, True
    )
    assert (await check_ifsc(_Directory(details), "HDFC0001234")).status == "verified"
    assert (await check_ifsc(_Directory(None), "HDFC0009999")).status == "not_found"
    down = _Directory(IfscLookupUnavailableError("down"))
    assert (await check_ifsc(down, "HDFC0001234")).status == "unavailable"


async def test_adapter_reads_branch_and_caches_it() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_HDFC)

    directory = _directory(httpx.MockTransport(handler))
    first = await directory.lookup("HDFC0001234")
    assert first is not None
    assert (first.bank, first.branch, first.upi) == ("HDFC Bank", "PARK STREET", True)
    await directory.lookup("HDFC0001234")
    assert calls == ["/HDFC0001234"]


async def test_adapter_404_means_no_such_branch() -> None:
    directory = _directory(httpx.MockTransport(lambda _: httpx.Response(404, text="Not Found")))
    assert await directory.lookup("HDFC0009999") is None


@pytest.mark.parametrize("response", [httpx.Response(503), httpx.ConnectError("boom")])
async def test_adapter_outage_is_unavailable_not_not_found(response: httpx.Response) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    directory = _directory(httpx.MockTransport(handler))
    with pytest.raises(IfscLookupUnavailableError):
        await directory.lookup("HDFC0001234")


def test_account_number_of_one_repeated_digit_is_refused() -> None:
    fields = {
        "account_holder": "Sai Gas Agency",
        "account_number": "000000000000",
        "ifsc": "HDFC0001234",
    }
    with pytest.raises(ValidationError):
        PaymentProfile.validated(**fields)
