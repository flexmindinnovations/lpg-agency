"""A driver's phone login is stored as E.164 and found whichever way it was saved."""

from __future__ import annotations

import pytest

from lpg.api.v1.schemas.employee import RegisterEmployeeRequest, UpdateEmployeeRequest
from lpg.infrastructure.persistence.repositories.identity import _phone_lookup_forms

_BASE = {"branch_id": "b", "first_name": "A", "last_name": "B", "role": "driver"}


@pytest.mark.parametrize(
    "typed", ["8484848484", "08484848484", "91 84848 48484", "+91-84848-48484"]
)
def test_registering_an_employee_stores_the_number_as_e164(typed: str) -> None:
    assert RegisterEmployeeRequest(**_BASE, phone_number=typed).phone_number == "+918484848484"


def test_updating_an_employee_stores_the_number_as_e164() -> None:
    assert UpdateEmployeeRequest(**_BASE, phone_number="8484848484").phone_number == "+918484848484"


def test_an_indian_number_is_also_looked_up_as_ten_digits() -> None:
    # Logins created before numbers were normalised hold the number as typed.
    assert _phone_lookup_forms("+918484848484") == ["+918484848484", "8484848484"]


def test_other_numbers_are_looked_up_as_given() -> None:
    assert _phone_lookup_forms("+14155550123") == ["+14155550123"]
