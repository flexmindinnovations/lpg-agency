"""Which accounts may sign in to which mobile app.

A phone number has one login per agency, with one role, and each app serves one
kind of user. The app names itself in the `X-App-Type` header.

**A refusal must not be recognisable.** Sign-in and refresh answer an account in
the wrong app exactly as they answer one that does not exist: the same error
code, status and message. Anything else would tell a stranger that the account
is real and what kind it is. Only the security event log records `wrong_app`.

This keeps people out of an app that cannot work for them; it is not what
protects data. Permissions come from the account's role whichever client asks,
so a client that sends no app name (the web dashboard, or a Customer app built
before it sent one) is not restricted here.
"""

from __future__ import annotations

CUSTOMER_APP = "customer_app"
DRIVER_APP = "driver_app"
ADMIN_APP = "admin_app"
MOBILE_APPS = frozenset({CUSTOMER_APP, DRIVER_APP, ADMIN_APP})

_CUSTOMER_ROLE = "customer"
_DRIVER_ROLE = "driver"


def app_admits(app: str | None, role: str) -> bool:
    if app == CUSTOMER_APP:
        return role == _CUSTOMER_ROLE
    if app == DRIVER_APP:
        return role == _DRIVER_ROLE
    if app == ADMIN_APP:
        return role not in (_CUSTOMER_ROLE, _DRIVER_ROLE)
    return True
