"""`_jsonable` — the value coercion `AuditRecorder` applies to every mapped
column before writing it into `audit.audit_log`'s JSONB `before_state`/
`after_state` columns.

Regression coverage for a real bug: a plain `date` column (e.g.
`Driver.license_expiry_date`) fell through `_jsonable` unchanged because
only `datetime` was handled, then failed with
`TypeError: Object of type date is not JSON serializable` when SQLAlchemy
tried to bind it to the JSONB parameter — surfaced as a 500 on
`PATCH /drivers/{id}/status`, unrelated to the driver-status update itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from lpg.infrastructure.persistence.audit import _jsonable


class TestJsonable:
    def test_uuid_becomes_str(self) -> None:
        value = uuid.uuid4()
        assert _jsonable(value) == str(value)

    def test_datetime_becomes_isoformat_str(self) -> None:
        value = datetime(2026, 8, 21, 15, 8, 59, tzinfo=UTC)
        assert _jsonable(value) == value.isoformat()

    def test_plain_date_becomes_isoformat_str(self) -> None:
        value = date(2028, 6, 30)
        assert _jsonable(value) == "2028-06-30"

    def test_decimal_becomes_str_not_float(self) -> None:
        """`str`, not `float` — an audit trail must not silently round a
        financial/measurement value."""
        value = Decimal("47.500")
        assert _jsonable(value) == "47.500"
        assert isinstance(_jsonable(value), str)

    def test_other_values_pass_through_unchanged(self) -> None:
        assert _jsonable("active") == "active"
        assert _jsonable(42) == 42
        assert _jsonable(None) is None
