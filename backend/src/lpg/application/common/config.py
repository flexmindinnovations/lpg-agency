"""Shared helpers for reading `TenantConfiguration` values.

Promoted out of `application/ai/use_cases.py` (ADR-045) once a second real
consumer (`application/delivery/auto_assignment.py`'s kill switch) needed
the exact same helper — a second caller is the signal a helper should stop
being module-private.
"""

from __future__ import annotations


def is_truthy_config_value(value: object) -> bool:
    """`TenantConfiguration.config_value` is `jsonb` and the generic Set
    Value admin form (no dedicated toggle UI for most boolean keys) sends
    whatever string the operator typed, not a JSON boolean — so a stored
    value of `"false"` is a real, live possibility, not a hypothetical.
    Plain `bool(value)` is wrong here: `bool("false")` is `True` in Python,
    since it only checks for a non-empty string. Confirmed live once
    already (ADR-045): setting `ai_gateway_enabled` to the literal text
    "false" through the real admin UI and asking a question came back
    answered, not disabled, before this helper existed. Every new
    boolean-shaped `TenantConfiguration` kill switch must use this, not a
    naive `bool(value)`.
    """
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no")
    return bool(value)
