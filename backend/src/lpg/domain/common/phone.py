"""Phone-number normalisation for an India-first product.

Customers and drivers type their mobile number however they are used to:
`9876543210`, `09876543210`, `919876543210` or `+91 98765 43210`. Stored
numbers are E.164 (`+919876543210`), so every entry point that looks a user
up by phone normalises first; otherwise the OTP key, the dev inbox and the
user lookup would each see a different string for the same person.
"""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[\s\-().]")
_INDIA_COUNTRY_CODE = "91"
_NATIONAL_LENGTH = 10


def normalize_phone_number(raw: str) -> str:
    """Return `raw` as E.164, assuming India when no country code is given.

    Input that already starts with `+` keeps its own country code (only the
    separators are dropped). Anything that is not a recognisable Indian
    form is returned with separators removed and left for the caller's own
    validation to reject.
    """
    compact = _SEPARATORS.sub("", raw.strip())
    if compact.startswith("+") or not compact.isdigit():
        return compact
    if len(compact) == _NATIONAL_LENGTH:
        return f"+{_INDIA_COUNTRY_CODE}{compact}"
    if len(compact) == _NATIONAL_LENGTH + 1 and compact.startswith("0"):
        return f"+{_INDIA_COUNTRY_CODE}{compact[1:]}"
    if len(compact) == _NATIONAL_LENGTH + len(_INDIA_COUNTRY_CODE) and compact.startswith(
        _INDIA_COUNTRY_CODE
    ):
        return f"+{compact}"
    return compact
