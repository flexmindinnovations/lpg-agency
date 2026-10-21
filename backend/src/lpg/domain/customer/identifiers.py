"""Format and checksum rules for the Indian identifiers a customer record
carries: KYC document numbers (Aadhaar, PAN, Voter ID, Driving Licence,
Passport), GSTIN and the postal PIN code.

Pure functions, no I/O. Each `normalize_*` returns the canonical stored form
(upper case, separators removed) or raises a `DomainError` subclass whose
message is safe to show to staff and customers as-is.
"""

from __future__ import annotations

import re

from lpg.domain.common.base import InvariantViolation


class InvalidIdentifierError(InvariantViolation):
    """A document number, GSTIN or PIN code is not in a valid format."""

    error_code = "INVALID_IDENTIFIER"


# ---------------------------------------------------------------------------
# Aadhaar — 12 digits, never starting with 0 or 1, last digit a Verhoeff
# check digit (UIDAI).
# ---------------------------------------------------------------------------

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_is_valid(digits: str) -> bool:
    check = 0
    for position, char in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[position % 8][int(char)]]
    return check == 0


def verhoeff_check_digit(digits: str) -> str:
    """The digit that makes `digits + check` pass `verhoeff_is_valid`."""
    check = 0
    for position, char in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[(position + 1) % 8][int(char)]]
    return str(_VERHOEFF_INV[check])


_AADHAAR_RE = re.compile(r"^[2-9]\d{11}$")

# ---------------------------------------------------------------------------
# Other KYC documents.
# ---------------------------------------------------------------------------

#: PAN: 5 letters (the 4th is the holder type — P individual, C company, H
#: HUF, F firm, A AOP, T trust, B BOI, L local authority, J artificial
#: juridical person, G government), 4 digits, 1 letter.
_PAN_RE = re.compile(r"^[A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z]$")
#: Voter ID (EPIC): 3 letters + 7 digits.
_VOTER_ID_RE = re.compile(r"^[A-Z]{3}\d{7}$")
#: Passport: 1 letter + 7 digits.
_PASSPORT_RE = re.compile(r"^[A-Z]\d{7}$")
#: Driving licence: 2-letter state code, 2-digit RTO code, then 11 more
#: characters in the current format (year + serial); older licences carry
#: letters in the serial, so 9 to 13 alphanumerics are accepted after the RTO.
_DRIVING_LICENCE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{9,13}$")

_SEPARATORS_RE = re.compile(r"[\s\-/]")

#: Document types a customer can submit, with how each is named in messages.
KYC_DOCUMENT_TYPES: dict[str, str] = {
    "aadhaar": "Aadhaar number",
    "pan": "PAN",
    "voter_id": "Voter ID (EPIC) number",
    "driving_license": "Driving licence number",
    "passport": "Passport number",
}

_KYC_FORMAT_HINTS: dict[str, tuple[re.Pattern[str], str]] = {
    "pan": (_PAN_RE, "10 characters like ABCPE1234F"),
    "voter_id": (_VOTER_ID_RE, "3 letters followed by 7 digits"),
    "passport": (_PASSPORT_RE, "1 letter followed by 7 digits"),
    "driving_license": (_DRIVING_LICENCE_RE, "like MH12 20110012345"),
}


def normalize_kyc_document_number(doc_type: str, document_number: str) -> str:
    """Validate a KYC document number for its type and return the stored form."""
    kind = doc_type.strip().lower()
    if kind not in KYC_DOCUMENT_TYPES:
        supported = ", ".join(sorted(KYC_DOCUMENT_TYPES))
        msg = f"Unsupported KYC document type '{doc_type}'. Use one of: {supported}."
        raise InvalidIdentifierError(msg, field="doc_type")

    value = _SEPARATORS_RE.sub("", document_number).upper()
    if kind == "aadhaar":
        if not _AADHAAR_RE.match(value) or not verhoeff_is_valid(value):
            msg = "Aadhaar number must be a valid 12-digit number."
            raise InvalidIdentifierError(msg, field="document_number")
        return value

    pattern, hint = _KYC_FORMAT_HINTS[kind]
    if not pattern.match(value):
        msg = f"{KYC_DOCUMENT_TYPES[kind]} must be {hint}."
        raise InvalidIdentifierError(msg, field="document_number")
    return value


# ---------------------------------------------------------------------------
# GSTIN — 2-digit state code + PAN + entity number + 'Z' + check character.
# ---------------------------------------------------------------------------

_GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_character(first_fourteen: str) -> str:
    """The GSTN check character for the first 14 characters of a GSTIN."""
    total = 0
    for index, char in enumerate(first_fourteen):
        product = _GSTIN_ALPHABET.index(char) * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_ALPHABET[(36 - total % 36) % 36]


def normalize_gstin(value: str) -> str:
    gstin = _SEPARATORS_RE.sub("", value).upper()
    match = _GSTIN_RE.match(gstin)
    state_code = int(match.group(1)) if match else 0
    if match is None or not 1 <= state_code <= 38 or gstin_check_character(gstin[:14]) != gstin[14]:
        msg = "GSTIN must be a valid 15-character GST number, like 27AAPFU0939F1ZV."
        raise InvalidIdentifierError(msg, field="gstin")
    return gstin


# ---------------------------------------------------------------------------
# PIN code — 6 digits, never starting with 0.
# ---------------------------------------------------------------------------

_PINCODE_RE = re.compile(r"^[1-9]\d{5}$")


def normalize_pincode(value: str) -> str:
    pincode = re.sub(r"\s", "", value)
    if not _PINCODE_RE.match(pincode):
        msg = "PIN code must be 6 digits and cannot start with 0."
        raise InvalidIdentifierError(msg, field="pincode")
    return pincode
