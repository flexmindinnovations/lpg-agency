"""Human labels for audit rows — what the Audit Log's "Record" column shows.

An audit row names its record by table and id (``order`` / a UUID); an
office user recognises "ORD000027", "KA01AB1234" or "Meena Iyer
(CN-000001)" instead (QA UR-04, DA-25). The label is worked out from the
record's own column values, and for child rows (an order's status history,
a route stop, a payment) from the parent they belong to.

Pure functions over column dicts, so the same rules serve both paths:

- write time (``AuditRecorder``): the row's snapshot, with parents looked up
  among the objects already loaded in the flushing session — no extra query;
- read time (``SqlAlchemyAuditLogRepository``): rows written before this
  existed (or whose parent was not loaded) get labelled from their stored
  ``after_state``/``before_state``, with parents fetched in one query per
  table for the whole page.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

#: A record's own business identifier, most specific first.
_OWN_IDENTIFIERS = (
    "order_number",
    "invoice_number",
    "complaint_number",
    "credit_note_number",
    "grn_number",
    "handover_number",
    "registration_number",
    "serial_number",
    "asset_tag",
)

#: Foreign-key column -> the table it points at. Checked in this order for a
#: record with no identifier of its own (a status-history row, an order line).
PARENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("order_id", "order"),
    ("invoice_id", "invoice"),
    ("complaint_id", "complaint"),
    ("route_id", "route"),
    ("customer_id", "customer"),
    ("employee_id", "employee"),
    ("vehicle_id", "vehicle"),
    ("cylinder_type_id", "cylinder_type"),
)

_MAX_LENGTH = 200


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_day(value: object) -> str | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return None
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return None


def _person(values: Mapping[str, Any]) -> str | None:
    first, last = _text(values.get("first_name")), _text(values.get("last_name"))
    name = " ".join(part for part in (first, last) if part)
    return name or None


def _parent_label(
    values: Mapping[str, Any],
    lookup: Callable[[str, str], Mapping[str, Any] | None],
    *,
    depth: int,
) -> str | None:
    for column, table in PARENT_COLUMNS:
        parent_id = _text(values.get(column))
        if parent_id is None:
            continue
        parent = lookup(table, parent_id)
        if parent is not None:
            label = _label(table, parent, lookup, depth=depth + 1)
            if label:
                return label
    return None


def _label(
    table: str,
    values: Mapping[str, Any],
    lookup: Callable[[str, str], Mapping[str, Any] | None],
    *,
    depth: int,
) -> str | None:
    if table == "customer":
        name, number = _text(values.get("full_name")), _text(values.get("consumer_number"))
        if name and number:
            return f"{name} ({number})"
        return name or number
    if table == "employee":
        return _person(values) or _text(values.get("employee_code"))
    if table == "identity_user":
        return _text(values.get("email")) or _text(values.get("phone_number"))
    if table == "route":
        day = _format_day(values.get("route_date"))
        vehicle_id = _text(values.get("vehicle_id"))
        vehicle = lookup("vehicle", vehicle_id) if vehicle_id and depth < 2 else None
        registration = _text(vehicle.get("registration_number")) if vehicle else None
        parts = [p for p in (f"Trip on {day}" if day else "Trip", registration) if p]
        return " · ".join(parts)
    if table == "driver":
        employee_id = _text(values.get("employee_id"))
        employee = lookup("employee", employee_id) if employee_id and depth < 2 else None
        return (_person(employee) if employee else None) or _text(values.get("license_number"))

    for column in _OWN_IDENTIFIERS:
        identifier = _text(values.get(column))
        if identifier:
            return identifier
    own_name = _text(values.get("name")) or _text(values.get("full_name"))
    if own_name:
        return own_name
    if depth >= 2:
        return None
    return _parent_label(values, lookup, depth=depth)


def audit_label(
    table: str,
    values: Mapping[str, Any] | None,
    lookup: Callable[[str, str], Mapping[str, Any] | None],
) -> str | None:
    """The label for one record, or ``None`` when nothing recognisable exists."""
    if not values:
        return None
    label = _label(table, values, lookup, depth=0)
    return label[:_MAX_LENGTH] if label else None


def parent_references(values: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """The (table, id) pairs ``audit_label`` may look up for these values."""
    if not values:
        return []
    refs = []
    for column, table in PARENT_COLUMNS:
        parent_id = _text(values.get(column))
        if parent_id:
            refs.append((table, parent_id))
    return refs
