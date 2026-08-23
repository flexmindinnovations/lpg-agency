"""Pure, no-I/O parsing of Aadhaar/PAN fields from raw OCR text.

Python port of `document-kyc-parser.ts` (the client-side OCR pass) — kept
behaviorally identical on purpose, so the frontend's fast client-side guess
and the backend's more-accurate second pass never disagree on *how* a field
is extracted, only on how well the underlying OCR read the image.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# Aadhaar: 12 digits, printed on the card in three groups of 4 (with or
# without the spaces surviving OCR). The separator is deliberately
# `[ \t]?`, not `\s?` — `\s` also matches newlines, which would let this
# match span two unrelated OCR lines (e.g. the trailing digits of a DOB
# year plus the start of the real Aadhaar number on the next line).
_AADHAAR_REGEX = re.compile(r"\b(\d{4}[ \t]?\d{4}[ \t]?\d{4})\b")

# PAN: 10-char alphanumeric, fixed format AAAAA9999A.
_PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", re.IGNORECASE)

# DD/MM/YYYY or DD-MM-YYYY, the standard print format on both card types.
_DOB_REGEX = re.compile(r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4})\b")

# Aadhaar cards also print an unrelated "Aadhaar no. issued: DD/MM/YYYY"
# date (often in a vertical sidebar), which is the same DD/MM/YYYY shape as
# the actual date of birth. A bare "first date in the text" search picks
# whichever one the OCR engine happens to read first — frequently the wrong
# one — so DOB extraction must actively avoid "issued" lines and prefer a
# line explicitly labeled as the date of birth.
_DOB_LABEL_LINE = re.compile(r"dob|date\s*of\s*birth|birth", re.IGNORECASE)
_ISSUED_LINE = re.compile(r"issued", re.IGNORECASE)

# Lines that are boilerplate/labels rather than the cardholder's name —
# filtered out before guessing which line the name is.
_NOISE_LINE = re.compile(
    r"government|india|income\s*tax|department|male|female|dob|"
    r"year of birth|permanent account number|signature",
    re.IGNORECASE,
)
_YEAR_OF_BIRTH_LINE = re.compile(r"year of birth", re.IGNORECASE)
_NAME_LINE_SHAPE = re.compile(r"^[A-Za-z][A-Za-z .]*$")

# Address block: Aadhaar prints it as a labeled, multi-line block ("Address:"
# on its own line or followed inline by the first line of the address).
# There is no fixed line count or delimiter, so the block is bounded by
# scanning forward from the label until a line that clearly isn't address
# text anymore (the Aadhaar/VID number, the UIDAI helpline/email/website
# footer) — capped at a handful of lines as a backstop against a mis-scan.
_ADDRESS_LABEL_LINE = re.compile(r"^address\s*[:\-]?\s*(.*)$", re.IGNORECASE)
_ADDRESS_STOP_LINE = re.compile(
    r"\bvid\b|help@|www\.|^1947$|^\d{4}[ \t]?\d{4}[ \t]?\d{4}$",
    re.IGNORECASE,
)
_ADDRESS_BLOCK_MAX_LINES = 6

_PINCODE_REGEX = re.compile(r"\b(\d{6})\b")
_DISTRICT_LABEL_REGEX = re.compile(r"\bdist\.?\s*[:\-]?\s*([^,\n]+)", re.IGNORECASE)
_POST_OFFICE_LABEL_REGEX = re.compile(r"\bpo\.?\s*[:\-]?\s*([^,\n]+)", re.IGNORECASE)
_LANDMARK_REGEX = re.compile(r"\b(?:near|opp\.?|opposite)\s+([^,\n]+)", re.IGNORECASE)

# Closed set of India's states/UTs — matched by exact name rather than
# guessed from position, since it's the one address component this parser
# can identify with real confidence. Sorted longest-first so "Andaman and
# Nicobar Islands" is tried before a shorter name that could coincidentally
# be a substring of it.
_INDIAN_STATES_AND_UTS = tuple(
    sorted(
        (
            "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
            "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
            "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
            "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
            "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
            "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
            "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
            "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
        ),
        key=len,
        reverse=True,
    )
)


@dataclass(frozen=True, slots=True)
class ParsedAddress:
    line_1: str | None
    line_2: str | None
    landmark: str | None
    area: str | None
    city: str | None
    district: str | None
    state: str | None
    pincode: str | None


@dataclass(frozen=True, slots=True)
class ParsedIdentityDocument:
    doc_type: str | None
    document_number: str | None
    full_name: str | None
    date_of_birth: date | None
    address: ParsedAddress | None


def parse_kyc_document(raw_text: str) -> ParsedIdentityDocument:
    """Extracts a document type + number, and best-effort a name, date of
    birth, and address, from raw OCR text. Aadhaar is checked first — a
    PAN-shaped substring can appear coincidentally inside a longer digit run
    OCR misreads, but a clean 12-digit Aadhaar match is a stronger signal on
    the documents this wizard supports today.

    Name and address extraction are heuristics, not guarantees — see
    `_guess_full_name` and `_parse_address`. Every field this function
    returns is still shown to the user as an editable, reviewable form
    field before submission, not written straight through.
    """
    aadhaar_match = _AADHAAR_REGEX.search(raw_text)
    pan_match = _PAN_REGEX.search(raw_text)

    if aadhaar_match:
        doc_type = "aadhaar"
        document_number: str | None = re.sub(r"\s", "", aadhaar_match.group(1))
    elif pan_match:
        doc_type = "pan"
        document_number = pan_match.group(1).upper()
    else:
        doc_type = None
        document_number = None

    date_of_birth = _guess_date_of_birth(raw_text)
    full_name = _guess_full_name(raw_text)
    address = _parse_address(raw_text)

    return ParsedIdentityDocument(
        doc_type=doc_type,
        document_number=document_number,
        full_name=full_name,
        date_of_birth=date_of_birth,
        address=address,
    )


def _date_from_match(match: re.Match[str]) -> date | None:
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _find_dob_line_index(lines: list[str]) -> int:
    """Locates the line most likely to hold the actual date of birth,
    preferring an explicit DOB/"date of birth" label and always skipping
    "issued" lines (see `_DOB_LABEL_LINE`/`_ISSUED_LINE` above). Falls back
    to any date-shaped line, then to a "year of birth"-only line (PAN cards
    sometimes print only the year), still skipping "issued" lines.
    """
    for i, line in enumerate(lines):
        if (
            not _ISSUED_LINE.search(line)
            and _DOB_LABEL_LINE.search(line)
            and _DOB_REGEX.search(line)
        ):
            return i
    for i, line in enumerate(lines):
        if not _ISSUED_LINE.search(line) and _DOB_REGEX.search(line):
            return i
    for i, line in enumerate(lines):
        if not _ISSUED_LINE.search(line) and _YEAR_OF_BIRTH_LINE.search(line):
            return i
    return -1


def _guess_date_of_birth(raw_text: str) -> date | None:
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    index = _find_dob_line_index(lines)
    if index == -1:
        return None
    match = _DOB_REGEX.search(lines[index])
    return _date_from_match(match) if match else None


def _is_plausible_name(line: str) -> bool:
    """A line is only accepted as a name if every "word" in it looks like a
    real word — at least 2 letters, containing a vowel — not just an
    all-letters regex match. Short OCR noise fragments (`w`, `ww`, `Aw`)
    pass a bare `[A-Za-z]+` test but fail this: single-letter tokens are
    rejected outright, and multi-letter tokens with no vowel (`ww`, `xr`)
    essentially never occur in a real name.
    """
    if len(line) < 3 or len(line) > 60:
        return False
    if _NOISE_LINE.search(line):
        return False
    if not _NAME_LINE_SHAPE.match(line):
        return False

    words = [w for w in line.split() if w]
    if len(words) < 2:  # require at least a first + last name
        return False
    for word in words:
        letters = word.replace(".", "")
        if len(letters) < 2 or not re.search(r"[aeiouAEIOU]", letters):
            return False
    return True


def _extract_address_block(lines: list[str]) -> str | None:
    start_index = None
    first_line_remainder = ""
    for i, line in enumerate(lines):
        match = _ADDRESS_LABEL_LINE.match(line)
        if match:
            start_index = i
            first_line_remainder = match.group(1).strip()
            break
    if start_index is None:
        return None

    block_lines = [first_line_remainder] if first_line_remainder else []
    for line in lines[start_index + 1 : start_index + 1 + _ADDRESS_BLOCK_MAX_LINES]:
        if _ADDRESS_STOP_LINE.search(line):
            break
        block_lines.append(line)

    block_lines = [line for line in block_lines if line]
    return "\n".join(block_lines) if block_lines else None


def _parse_address(raw_text: str) -> ParsedAddress | None:
    """Splits the Aadhaar address block into the fields the onboarding
    wizard's Address step actually has. There's no fixed format to parse
    against — freeform, often bilingual text — so this pulls out the pieces
    it can identify with a real signal (an explicit label, or a closed set
    like state names) and treats what's left as line_1/line_2/area by
    position. It gets city/district/state/pincode right far more reliably
    than area/landmark, which is inherent to how little structure the
    source text carries — not a reason to skip the fields it does get
    right.
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    block = _extract_address_block(lines)
    if block is None:
        return None

    block_lines = [line for line in block.split("\n") if line.strip()]
    line_1 = (block_lines[0].strip(" ,.-") or None) if block_lines else None
    residual = ", ".join(block_lines[1:])

    pincode_match = _PINCODE_REGEX.search(residual)
    pincode = pincode_match.group(1) if pincode_match else None
    if pincode_match:
        residual = residual[: pincode_match.start()] + residual[pincode_match.end() :]

    state = None
    for name in _INDIAN_STATES_AND_UTS:
        index = residual.lower().find(name.lower())
        if index != -1:
            state = name
            residual = residual[:index] + residual[index + len(name) :]
            break

    district = None
    district_match = _DISTRICT_LABEL_REGEX.search(residual)
    if district_match:
        district = district_match.group(1).strip(" .,-") or None
        residual = residual[: district_match.start()] + residual[district_match.end() :]

    city = None
    post_office_match = _POST_OFFICE_LABEL_REGEX.search(residual)
    if post_office_match:
        city = post_office_match.group(1).strip(" .,-") or None
        residual = residual[: post_office_match.start()] + residual[post_office_match.end() :]

    landmark = None
    landmark_match = _LANDMARK_REGEX.search(residual)
    if landmark_match:
        landmark = landmark_match.group(1).strip(" .,-") or None
        residual = residual[: landmark_match.start()] + residual[landmark_match.end() :]

    cleaned_residual = re.sub(r"\s*,\s*", ", ", residual).strip(" ,.-")
    segments = [seg.strip(" .-") for seg in cleaned_residual.split(",") if seg.strip(" .-")]
    area = segments[0] if segments else None
    line_2 = ", ".join(segments[1:]) if len(segments) > 1 else None

    if not any([line_1, line_2, area, city, district, state, pincode]):
        return None

    return ParsedAddress(
        line_1=line_1,
        line_2=line_2,
        landmark=landmark,
        area=area,
        city=city,
        district=district,
        state=state,
        pincode=pincode,
    )


def _guess_full_name(raw_text: str) -> str | None:
    lines = [line.strip() for line in raw_text.split("\n")]
    lines = [line for line in lines if line]

    # The name is printed immediately above the date of birth on both
    # Aadhaar and PAN layouts — a much stronger anchor than "first
    # plausible line in the whole document", which is prone to picking up
    # misread header/boilerplate text that happens to look word-shaped.
    dob_line_index = _find_dob_line_index(lines)
    if dob_line_index >= 0:
        for i in range(dob_line_index - 1, max(dob_line_index - 4, -1), -1):
            if _is_plausible_name(lines[i]):
                return lines[i]

    return next((line for line in lines if _is_plausible_name(line)), None)
