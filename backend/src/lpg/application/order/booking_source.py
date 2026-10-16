"""Which channel an order came in through, decided by the server.

The booking source used to be whatever the client sent, so a customer's app
could claim `staff` and a dashboard user could claim `mobile_app`. It is now
derived from who is booking: a `customer` login is the Customer App, and
everyone else is staff entering the booking on the dashboard. Staff may still
record the channel the customer actually used (`phone`, `walk_in`, `whatsapp`)
or `api` for an integration, but never `mobile_app`.
"""

from __future__ import annotations

from lpg.application.common.errors import ValidationError

#: Orders placed by a `customer` login, i.e. in the Customer App.
CUSTOMER_APP_SOURCE = "mobile_app"
#: Orders entered by staff on the dashboard when no other channel is recorded.
DASHBOARD_SOURCE = "staff"


def resolve_booking_source(role: str, requested: str | None) -> str:
    """The booking source to record for `role`, given what the client asked for."""
    if role == "customer":
        return CUSTOMER_APP_SOURCE
    if requested is None:
        return DASHBOARD_SOURCE
    if requested == CUSTOMER_APP_SOURCE:
        msg = "The 'mobile_app' source is reserved for orders placed in the Customer App."
        raise ValidationError(msg, errors={"booking_source": [msg]})
    return requested
