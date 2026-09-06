"""Unit tests for the DL / RC OCR field parser (pure, no I/O)."""

from __future__ import annotations

import re
from datetime import date

import pytest

from lpg.domain.delivery.compliance_document_parser import (
    parse_driving_licence,
    parse_vehicle_rc,
)

# --- representative synthetic OCR text (no real PII) -------------------------

_DL_CLEAN = """
UNION OF INDIA
DRIVING LICENCE
DL No : MH12 20110012345
Name : RAVI KUMAR SHARMA
DOB : 14-08-1988
Valid Till : 13-08-2028
Valid (TR) : 13-08-2026
COV : LMV MCWG TRANS
""".strip()

_DL_NOISY = """
DR1VING L1CENCE  UN10N 0F IND1A
DLNo  KA05-2019-0004567
NAME  ANITA  DESAI
D.O.B   02/01/1990
Valid Till   01/01/2030
""".strip()

_RC_CLEAN = """
CERTIFICATE OF REGISTRATION
Regn No : MH 12 AB 1234
Name : SURESH BABU
Regn Date : 05-06-2021
Regn Valid Upto : 04-06-2036
Fitness Valid Upto : 04-06-2026
Insurance Upto : 30-04-2026
Chassis No : MA3ERLF1S00123456
Engine No : K12MN1234567
Fuel : PETROL/CNG
Maker / Model : MARUTI SUZUKI / EECO
""".strip()


class TestDrivingLicence:
    def test_extracts_number_name_and_validity_from_a_clean_read(self) -> None:
        parsed = parse_driving_licence(_DL_CLEAN)
        assert parsed.document_number == "MH1220110012345"
        assert parsed.holder_name == "Ravi Kumar Sharma"
        assert parsed.date_of_birth == date(1988, 8, 14)
        assert parsed.valid_till == date(2028, 8, 13)
        assert parsed.transport_valid_till == date(2026, 8, 13)
        assert "LMV" in parsed.vehicle_classes and "MCWG" in parsed.vehicle_classes

    def test_degrades_to_number_only_on_a_noisy_read(self) -> None:
        parsed = parse_driving_licence(_DL_NOISY)
        # The number's fixed shape still matches through the OCR noise…
        assert parsed.document_number == "KA0520190004567"
        # …the private validity is still label-anchored…
        assert parsed.valid_till == date(2030, 1, 1)

    def test_returns_all_none_for_unrelated_text(self) -> None:
        parsed = parse_driving_licence("this is not a licence at all")
        assert parsed.document_number is None
        assert parsed.holder_name is None
        assert parsed.valid_till is None


class TestVehicleRc:
    def test_extracts_plate_dates_and_identifiers_from_a_clean_read(self) -> None:
        parsed = parse_vehicle_rc(_RC_CLEAN)
        assert parsed.registration_number == "MH12AB1234"
        assert parsed.document_number == parsed.registration_number
        assert parsed.owner_name == "Suresh Babu"
        assert parsed.registration_date == date(2021, 6, 5)
        assert parsed.valid_upto == date(2036, 6, 4)
        assert parsed.fitness_upto == date(2026, 6, 4)
        assert parsed.insurance_upto == date(2026, 4, 30)
        assert parsed.chassis_number == "MA3ERLF1S00123456"
        assert parsed.engine_number == "K12MN1234567"
        assert parsed.fuel_type == "PETROL/CNG"
        assert parsed.maker_model is not None and "MARUTI" in parsed.maker_model

    @pytest.mark.parametrize(
        ("plate_text", "expected"),
        [
            ("Regn No KA01MJ2345", "KA01MJ2345"),
            ("Regn No : TS 09 EQ 0420", "TS09EQ0420"),
            ("Regn No 22 BH 1234 AB", "22BH1234AB"),
        ],
    )
    def test_plate_format_variants(self, plate_text: str, expected: str) -> None:
        assert parse_vehicle_rc(plate_text).registration_number == expected

    def test_number_matches_the_plate_regex_shape(self) -> None:
        parsed = parse_vehicle_rc(_RC_CLEAN)
        assert parsed.registration_number is not None
        assert re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{3,4}", parsed.registration_number)
