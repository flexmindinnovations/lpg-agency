"""Pure, no-I/O parsing of Indian Driving Licence and Vehicle RC fields from
raw OCR text.

Same contract as ``domain/customer/kyc_document_parser.py``: every field this
returns is a *best-effort head start*, shown to the user as an editable,
reviewable form field before submission — never written straight through. On a
low-confidence read the caller should fall back to "we could read the number,
fill the rest by hand".

DL and RC layouts vary by issuing state and by the era the card was printed, so
these are heuristics tuned to the labels most cards actually carry, not a
grammar. The document *number* is the one field extracted structurally (fixed
character shape); everything else is label-anchored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

# DD-MM-YYYY / DD/MM/YYYY / DD.MM.YYYY — the print format on both card types.
_DATE_RE = re.compile(r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4})\b")

_NAME_LABEL_RE = re.compile(r"\bname\b", re.IGNORECASE)
_NAME_SHAPE_RE = re.compile(r"^[A-Za-z][A-Za-z .]{2,48}$")
_NOISE_NAME_RE = re.compile(
    r"government|india|transport|department|licence|license|authority|"
    r"union|state|father|mother|husband|son|daughter|address|"
    r"registration|certificate|vehicle",
    re.IGNORECASE,
)


def _date_from_match(match: re.Match[str]) -> date | None:
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _lines(raw_text: str) -> list[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _labelled_date(lines: list[str], label_re: re.Pattern[str]) -> date | None:
    """The first date on a line matching ``label_re``."""
    for line in lines:
        if label_re.search(line):
            match = _DATE_RE.search(line)
            if match:
                return _date_from_match(match)
    return None


def _guess_name(lines: list[str]) -> str | None:
    """Prefer a line explicitly labelled 'Name'; else the first plausible line."""
    for i, line in enumerate(lines):
        if _NAME_LABEL_RE.search(line) and not _NOISE_NAME_RE.search(line):
            # "Name : RAVI KUMAR" on one line, or the label then the value next.
            after = re.sub(r"^.*name\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
            if _NAME_SHAPE_RE.match(after) and " " in after:
                return _clean_name(after)
            if i + 1 < len(lines) and _NAME_SHAPE_RE.match(lines[i + 1]):
                return _clean_name(lines[i + 1])
    for line in lines:
        if _NAME_SHAPE_RE.match(line) and " " in line and not _NOISE_NAME_RE.search(line):
            return _clean_name(line)
    return None


def _clean_name(value: str) -> str:
    return " ".join(value.split()).title()


# ---------------------------------------------------------------------------
# Driving Licence
# ---------------------------------------------------------------------------

# SS RR YYYY NNNNNNN with optional separators, tolerating the year+serial
# running together (e.g. "MH1220110012345", "KA05 20190004567", "DL-0420110012345").
_DL_NUMBER_RE = re.compile(r"\b([A-Z]{2}[-\s]?\d{1,2}[-\s]?(?:19|20)?\d{2}[-\s]?\d{7,11})\b")
_DL_VALID_TILL_RE = re.compile(r"valid\s*(?:till|upto|up to)|valid\s*\(?\s*nt", re.IGNORECASE)
_DL_TRANSPORT_VALID_RE = re.compile(r"valid\s*\(?\s*tr|transport", re.IGNORECASE)
_DL_DOB_RE = re.compile(r"\bdob\b|date\s*of\s*birth", re.IGNORECASE)
_DL_COV_RE = re.compile(
    r"\b(MCWG|MCWOG|LMV|LMV-?NT|LMV-?TR|MGV|HGMV|HPMV|HTV|TRANS|TRACTOR|"
    r"3W|3WNT|3WT|INVCRG)\b"
)


@dataclass(frozen=True, slots=True)
class ParsedDrivingLicence:
    document_number: str | None
    holder_name: str | None
    date_of_birth: date | None
    valid_till: date | None
    transport_valid_till: date | None
    vehicle_classes: tuple[str, ...]


def parse_driving_licence(raw_text: str) -> ParsedDrivingLicence:
    """Extract driving-licence fields. ``valid_till`` is the private (NT)
    validity; ``transport_valid_till`` the shorter commercial (TR) one when the
    card prints both."""
    text = raw_text.upper()
    lines = _lines(raw_text)

    number_match = _DL_NUMBER_RE.search(text)
    document_number = re.sub(r"[-\s]+", "", number_match.group(1)) if number_match else None

    valid_till = _labelled_date(lines, _DL_VALID_TILL_RE)
    transport_valid_till = _labelled_date(lines, _DL_TRANSPORT_VALID_RE)
    date_of_birth = _labelled_date(lines, _DL_DOB_RE)

    classes = tuple(dict.fromkeys(_DL_COV_RE.findall(text)))

    return ParsedDrivingLicence(
        document_number=document_number,
        holder_name=_guess_name(lines),
        date_of_birth=date_of_birth,
        valid_till=valid_till,
        transport_valid_till=transport_valid_till,
        vehicle_classes=classes,
    )


# ---------------------------------------------------------------------------
# Vehicle Registration Certificate (RC)
# ---------------------------------------------------------------------------

# BH series first (DD BH NNNN LL, e.g. "22 BH 1234 AB") so a "<label> 22 BH…"
# run isn't consumed by the standard SS-DD-L-NNNN branch; then the standard
# plate (e.g. "MH 12 AB 1234", "KA01MJ2345").
_RC_PLATE_RE = r"\d{2}\s?BH\s?\d{4}\s?[A-Z]{1,2}|[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4}"
# Prefer the plate that follows an explicit "Regn No" label; fall back to the
# first plate-shaped token anywhere.
_RC_NUMBER_LABELLED_RE = re.compile(
    rf"(?:REGN|REGISTRATION)\s*(?:NO|NUMBER|\.)?\s*[:\-]?\s*({_RC_PLATE_RE})"
)
_RC_NUMBER_RE = re.compile(rf"\b({_RC_PLATE_RE})\b")
_RC_VALID_UPTO_RE = re.compile(
    r"regn?\s*valid|registration\s*valid|valid\s*(?:till|upto|up to)", re.IGNORECASE
)
_RC_FITNESS_RE = re.compile(r"fitness|f\.?c\.?\s*valid", re.IGNORECASE)
_RC_INSURANCE_RE = re.compile(r"insurance|policy\s*valid|ins\.?\s*upto", re.IGNORECASE)
_RC_REGN_DATE_RE = re.compile(r"regn?\s*(?:date|dt)|date\s*of\s*regn", re.IGNORECASE)
_RC_CHASSIS_RE = re.compile(
    r"chassis\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Z0-9]{6,25})", re.IGNORECASE
)
_RC_ENGINE_RE = re.compile(r"engine\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Z0-9]{5,25})", re.IGNORECASE)
_RC_FUEL_RE = re.compile(r"\b(PETROL/CNG|PETROL/LPG|PETROL|DIESEL|CNG|LPG|ELECTRIC|HYBRID)\b")
_RC_MAKER_RE = re.compile(
    r"(?:maker|mfr|manufacturer)\s*(?:name|/\s*model)?\s*[:\-]?\s*(.+)", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class ParsedVehicleRc:
    document_number: str | None
    registration_number: str | None
    owner_name: str | None
    registration_date: date | None
    valid_upto: date | None
    fitness_upto: date | None
    insurance_upto: date | None
    chassis_number: str | None
    engine_number: str | None
    fuel_type: str | None
    maker_model: str | None


def parse_vehicle_rc(raw_text: str) -> ParsedVehicleRc:
    """Extract RC fields. ``document_number`` and ``registration_number`` are
    the same value (the plate) — both are returned so the caller can populate a
    generic "document number" field and the vehicle's own registration field
    from one read."""
    text = raw_text.upper()
    lines = _lines(raw_text)

    number_match = _RC_NUMBER_LABELLED_RE.search(text) or _RC_NUMBER_RE.search(text)
    registration_number = re.sub(r"\s+", "", number_match.group(1)) if number_match else None

    chassis_match = _RC_CHASSIS_RE.search(raw_text)
    engine_match = _RC_ENGINE_RE.search(raw_text)
    fuel_match = _RC_FUEL_RE.search(text)
    maker_match = _RC_MAKER_RE.search(raw_text)

    return ParsedVehicleRc(
        document_number=registration_number,
        registration_number=registration_number,
        owner_name=_guess_name(lines),
        registration_date=_labelled_date(lines, _RC_REGN_DATE_RE),
        valid_upto=_labelled_date(lines, _RC_VALID_UPTO_RE),
        fitness_upto=_labelled_date(lines, _RC_FITNESS_RE),
        insurance_upto=_labelled_date(lines, _RC_INSURANCE_RE),
        chassis_number=chassis_match.group(1).upper() if chassis_match else None,
        engine_number=engine_match.group(1).upper() if engine_match else None,
        fuel_type=fuel_match.group(1) if fuel_match else None,
        maker_model=" ".join(maker_match.group(1).split())[:80] if maker_match else None,
    )
