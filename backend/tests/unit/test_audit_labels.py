"""`audit_label` — the human label the Audit Log shows for a record."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpg.infrastructure.persistence.audit_labels import audit_label, parent_references

if TYPE_CHECKING:
    from collections.abc import Mapping

ORDER_ID = "6e2c4f8a-0000-4000-8000-000000000001"
VEHICLE_ID = "6e2c4f8a-0000-4000-8000-000000000002"
ROUTE_ID = "6e2c4f8a-0000-4000-8000-000000000003"
EMPLOYEE_ID = "6e2c4f8a-0000-4000-8000-000000000004"

PARENTS: dict[tuple[str, str], Mapping[str, Any]] = {
    ("order", ORDER_ID): {"id": ORDER_ID, "order_number": "ORD000027"},
    ("vehicle", VEHICLE_ID): {"id": VEHICLE_ID, "registration_number": "KA01AB1234"},
    ("route", ROUTE_ID): {"id": ROUTE_ID, "route_date": "2026-10-20", "vehicle_id": VEHICLE_ID},
    ("employee", EMPLOYEE_ID): {"id": EMPLOYEE_ID, "first_name": "Ravi", "last_name": "Kumar"},
}


def lookup(table: str, entity_id: str) -> Mapping[str, Any] | None:
    return PARENTS.get((table, entity_id))


def none(_table: str, _entity_id: str) -> None:
    return None


def test_records_with_their_own_number() -> None:
    assert audit_label("order", {"order_number": "ORD000027"}, none) == "ORD000027"
    assert audit_label("invoice", {"invoice_number": "INV-0001"}, none) == "INV-0001"
    assert audit_label("vehicle", {"registration_number": "KA01AB1234"}, none) == "KA01AB1234"
    assert audit_label("branch", {"name": "Gachibowli"}, none) == "Gachibowli"


def test_customer_shows_name_and_consumer_number() -> None:
    values = {"full_name": "Meena Iyer", "consumer_number": "CN-000001"}
    assert audit_label("customer", values, none) == "Meena Iyer (CN-000001)"


def test_child_rows_take_their_parent_label() -> None:
    history = {"order_id": ORDER_ID, "from_status": "booked", "to_status": "confirmed"}
    assert audit_label("order_status_history", history, lookup) == "ORD000027"
    assert audit_label("cancellation_record", {"order_id": ORDER_ID}, lookup) == "ORD000027"


def test_route_and_route_stop_name_the_trip_and_van() -> None:
    route = PARENTS[("route", ROUTE_ID)]
    assert audit_label("route", route, lookup) == "Trip on 20 Oct 2026 · KA01AB1234"
    stop = {"route_id": ROUTE_ID, "order_id": None, "sequence_number": 1}
    assert audit_label("route_stop", stop, lookup) == "Trip on 20 Oct 2026 · KA01AB1234"


def test_driver_uses_the_employee_name() -> None:
    driver = {"employee_id": EMPLOYEE_ID, "license_number": "DL-1"}
    assert audit_label("driver", driver, lookup) == "Ravi Kumar"
    assert audit_label("driver", driver, none) == "DL-1"


def test_nothing_recognisable_gives_none() -> None:
    assert audit_label("order_status_history", {"order_id": ORDER_ID}, none) is None
    assert audit_label("order", None, none) is None


def test_parent_references_lists_foreign_keys() -> None:
    assert parent_references({"order_id": ORDER_ID, "route_id": None}) == [("order", ORDER_ID)]
