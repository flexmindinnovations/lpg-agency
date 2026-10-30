"""IFSC directory over Razorpay's public IFSC API (https://ifsc.razorpay.com).

Free, keyless and not tied to the agency's Razorpay account. A 404 means no
branch holds the code; anything else that goes wrong is "unavailable", so an
outage there never blocks an agency from saving its details.
"""

from __future__ import annotations

import httpx

from lpg.application.accounting.payment_verification import (
    IfscDetails,
    IfscLookupUnavailableError,
)
from lpg.config.logging import get_logger

_logger = get_logger(__name__)

_BASE_URL = "https://ifsc.razorpay.com"
_TIMEOUT_SECONDS = 4.0


class RazorpayIfscDirectory:
    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._transport = transport
        #: Branch data barely changes; keep answers for the life of the process.
        self._found: dict[str, IfscDetails] = {}

    async def lookup(self, ifsc: str) -> IfscDetails | None:
        if ifsc in self._found:
            return self._found[ifsc]
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=_TIMEOUT_SECONDS
            ) as client:
                response = await client.get(f"{self._base_url}/{ifsc}")
        except httpx.HTTPError as exc:
            _logger.warning("ifsc_lookup_failed", ifsc=ifsc, error=str(exc))
            msg = "IFSC directory unreachable"
            raise IfscLookupUnavailableError(msg) from exc
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code != httpx.codes.OK:
            _logger.warning("ifsc_lookup_failed", ifsc=ifsc, status=response.status_code)
            msg = f"IFSC directory answered {response.status_code}"
            raise IfscLookupUnavailableError(msg)
        body = response.json()
        details = IfscDetails(
            ifsc=str(body.get("IFSC") or ifsc),
            bank=str(body.get("BANK") or ""),
            branch=str(body.get("BRANCH") or ""),
            city=str(body.get("CITY") or ""),
            state=str(body.get("STATE") or ""),
            address=str(body.get("ADDRESS") or ""),
            upi=bool(body.get("UPI")),
            neft=bool(body.get("NEFT")),
            imps=bool(body.get("IMPS")),
        )
        self._found[ifsc] = details
        return details
