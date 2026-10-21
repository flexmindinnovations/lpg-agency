"""Indian GST reference rules shared by the tenant, customer and accounting
contexts (BR-16, BR-31).

Only statutory *structure* lives here — GSTIN format and check digit, the
GST state-code table, HSN/SAC code shape, and how a line's tax splits into
CGST + SGST (intra-state) or IGST (inter-state). The *rates* are never
hardcoded: each tenant configures them on its cylinder types (BR-31,
D-42), and invoice generation refuses to run without one rather than
issuing a 0% invoice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from lpg.domain.common.base import InvariantViolation

#: GST state / union-territory codes — the first two digits of every GSTIN
#: and the "place of supply" code on a tax invoice (CBIC state code list).
GST_STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

#: Highest GST slab in force. A configured rate above it is a typo, not a slab.
MAX_GST_RATE_PERCENT = Decimal("28")

_CENT = Decimal("0.01")
_GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
#: HSN (goods) and SAC (services) codes are 4, 6 or 8 digits on an invoice.
_HSN_RE = re.compile(r"^(?:[0-9]{4}|[0-9]{6}|[0-9]{8})$")
_NON_ALNUM_RE = re.compile(r"[^a-z]")


def to_cents(amount: Decimal) -> Decimal:
    """Round a rupee amount to paise, half-up — how GST amounts are stated."""
    return amount.quantize(_CENT, rounding=ROUND_HALF_UP)


def gstin_check_character(first_fourteen: str) -> str:
    """The GSTIN's 15th character: a mod-36 checksum over the first 14."""
    total = 0
    for index, char in enumerate(first_fourteen):
        product = _GSTIN_CHARSET.index(char) * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_CHARSET[(36 - total % 36) % 36]


def normalize_gstin(value: str) -> str:
    """Upper-case, strip and validate a GSTIN; raise if it is not one.

    Checks the shape (state code, PAN, entity number, `Z`, check digit), that
    the state code is a real one, and the check digit itself, so a mistyped
    GSTIN is caught at entry rather than on a filed return.
    """
    gstin = value.strip().upper()
    if not _GSTIN_RE.match(gstin):
        msg = "GSTIN must be 15 characters, for example 36AABCS1429B1ZV."
        raise InvariantViolation(msg, gstin=gstin)
    if gstin[:2] not in GST_STATE_CODES:
        msg = f"GSTIN starts with '{gstin[:2]}', which is not a GST state code."
        raise InvariantViolation(msg, gstin=gstin)
    if gstin_check_character(gstin[:14]) != gstin[14]:
        msg = "GSTIN check digit does not match. Please re-check the number."
        raise InvariantViolation(msg, gstin=gstin)
    return gstin


def normalize_hsn_code(value: str) -> str:
    code = value.strip()
    if not _HSN_RE.match(code):
        msg = "HSN/SAC code must be 4, 6 or 8 digits."
        raise InvariantViolation(msg, hsn_code=code)
    return code


def validate_gst_rate(rate_percent: Decimal) -> Decimal:
    if rate_percent < 0 or rate_percent > MAX_GST_RATE_PERCENT:
        msg = f"GST rate must be between 0% and {MAX_GST_RATE_PERCENT}%."
        raise InvariantViolation(msg, gst_rate_percent=str(rate_percent))
    return rate_percent.quantize(_CENT)


def state_code_for(state: str | None) -> str | None:
    """The GST state code for a state given by code ("36") or by name
    ("Telangana", "tamil nadu"). `None` when it cannot be resolved.
    """
    if not state:
        return None
    cleaned = state.strip()
    if cleaned in GST_STATE_CODES:
        return cleaned
    wanted = _NON_ALNUM_RE.sub("", cleaned.lower())
    for code, name in GST_STATE_CODES.items():
        if _NON_ALNUM_RE.sub("", name.lower()) == wanted:
            return code
    return None


def state_name_for(code: str | None) -> str | None:
    return GST_STATE_CODES.get(code) if code else None


@dataclass(frozen=True, slots=True)
class GstSplit:
    """A line's tax split by head. Intra-state supply: CGST + SGST (half
    each, SGST taking the odd paisa). Inter-state: all IGST.
    """

    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @classmethod
    def of(cls, tax_amount: Decimal, *, inter_state: bool) -> GstSplit:
        zero = Decimal("0.00")
        if inter_state:
            return cls(cgst=zero, sgst=zero, igst=tax_amount)
        cgst = to_cents(tax_amount / 2)
        return cls(cgst=cgst, sgst=tax_amount - cgst, igst=zero)


def compute_line_tax(taxable_value: Decimal, rate_percent: Decimal) -> Decimal:
    return to_cents(taxable_value * rate_percent / Decimal("100"))


def split_inclusive(gross: Decimal, rate_percent: Decimal) -> tuple[Decimal, Decimal]:
    """Split a GST-inclusive amount into `(taxable_value, tax)`.

    The taxable value is `gross / (1 + rate)` rounded to paise, and the tax is
    whatever remains, so `taxable_value + tax == gross` to the paisa — the
    customer pays exactly the listed price.
    """
    gross = to_cents(gross)
    taxable = to_cents(gross * Decimal("100") / (Decimal("100") + rate_percent))
    return taxable, gross - taxable
