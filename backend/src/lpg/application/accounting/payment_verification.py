"""Checks on the agency's bank and UPI details (ADR-066, amended).

What can be verified without a payment-provider account:

- **IFSC** — looked up in a public bank-branch directory. A code no branch
  holds is a typo; a hit also gives the bank and branch to fill in.
- **UPI ID** — its shape, and whether the part after `@` is a handle a known
  bank or UPI app issues.

What cannot (the account exists, who owns it) needs a PSP's VPA-lookup or
penny-drop API, and the result below says so rather than implying it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

#: Handles issued by banks and UPI apps. A VPA on an unlisted handle may still
#: be real (new handles appear), so an unknown one is a warning, never an error.
UPI_HANDLES: dict[str, str] = {
    "ybl": "PhonePe (Yes Bank)",
    "ibl": "PhonePe (ICICI Bank)",
    "axl": "PhonePe (Axis Bank)",
    "okhdfcbank": "Google Pay (HDFC Bank)",
    "okicici": "Google Pay (ICICI Bank)",
    "oksbi": "Google Pay (State Bank of India)",
    "okaxis": "Google Pay (Axis Bank)",
    "paytm": "Paytm Payments Bank",
    "ptyes": "Paytm (Yes Bank)",
    "ptsbi": "Paytm (State Bank of India)",
    "pthdfc": "Paytm (HDFC Bank)",
    "ptaxis": "Paytm (Axis Bank)",
    "upi": "BHIM",
    "apl": "Amazon Pay",
    "yapl": "Amazon Pay",
    "waaxis": "WhatsApp Pay (Axis Bank)",
    "wahdfcbank": "WhatsApp Pay (HDFC Bank)",
    "wasbi": "WhatsApp Pay (State Bank of India)",
    "waicici": "WhatsApp Pay (ICICI Bank)",
    "freecharge": "Freecharge",
    "ikwik": "MobiKwik",
    "airtel": "Airtel Payments Bank",
    "jio": "Jio Payments Bank",
    "fbl": "Federal Bank",
    "hdfcbank": "HDFC Bank",
    "icici": "ICICI Bank",
    "sbi": "State Bank of India",
    "axisbank": "Axis Bank",
    "kotak": "Kotak Mahindra Bank",
    "indus": "IndusInd Bank",
    "idfcbank": "IDFC FIRST Bank",
    "yesbank": "Yes Bank",
    "pnb": "Punjab National Bank",
    "boi": "Bank of India",
    "barodampay": "Bank of Baroda",
    "cnrb": "Canara Bank",
    "unionbank": "Union Bank of India",
    "okbizaxis": "Google Pay for Business (Axis Bank)",
    "ucobank": "UCO Bank",
    "centralbank": "Central Bank of India",
    "iob": "Indian Overseas Bank",
    "aubank": "AU Small Finance Bank",
    "rbl": "RBL Bank",
    "sib": "South Indian Bank",
    "dbs": "DBS Bank",
    "hsbc": "HSBC",
    "citi": "Citibank",
    "sc": "Standard Chartered",
}


@dataclass(frozen=True, slots=True)
class UpiCheck:
    #: Always true here: a malformed ID is rejected before this runs.
    format_valid: bool
    handle: str
    #: Who issues the handle, when it is a known one.
    provider: str | None

    @property
    def handle_known(self) -> bool:
        return self.provider is not None


def check_upi_id(upi_id: str) -> UpiCheck:
    handle = upi_id.rpartition("@")[2].lower()
    return UpiCheck(format_valid=True, handle=handle, provider=UPI_HANDLES.get(handle))


@dataclass(frozen=True, slots=True)
class IfscDetails:
    ifsc: str
    bank: str
    branch: str
    city: str
    state: str
    address: str
    upi: bool
    neft: bool
    imps: bool


class IfscLookupUnavailableError(Exception):
    """The directory could not be reached; says nothing about the code."""


class IfscDirectory(Protocol):
    async def lookup(self, ifsc: str) -> IfscDetails | None:
        """The branch holding `ifsc`, or None when no branch does.

        Raises `IfscLookupUnavailableError` when the directory cannot answer.
        """
        ...


IfscStatus = Literal["verified", "not_found", "unavailable"]


@dataclass(frozen=True, slots=True)
class IfscCheck:
    status: IfscStatus
    details: IfscDetails | None = None


async def check_ifsc(directory: IfscDirectory, ifsc: str) -> IfscCheck:
    try:
        details = await directory.lookup(ifsc)
    except IfscLookupUnavailableError:
        return IfscCheck("unavailable")
    if details is None:
        return IfscCheck("not_found")
    return IfscCheck("verified", details)
