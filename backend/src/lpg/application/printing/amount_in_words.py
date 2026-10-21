"""Rupee amounts in words, Indian numbering (lakh, crore) — the "total in
words" line a GST tax invoice carries (DA-13).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_ONES = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")
#: (divisor, name), largest first. Above 99 crore the crore count recurses.
_SCALES = ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand"), (100, "Hundred"))


def _below_hundred(number: int) -> str:
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _words(number: int) -> str:
    if number == 0:
        return ""
    for divisor, name in _SCALES:
        if number >= divisor:
            head, rest = divmod(number, divisor)
            return f"{_words(head)} {name} {_words(rest)}".strip()
    return _below_hundred(number)


def rupees_in_words(amount: Decimal) -> str:
    """`Decimal("1234.50")` → "Rupees One Thousand Two Hundred Thirty Four
    and Fifty Paise Only".
    """
    paise_total = int((abs(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    rupees, paise = divmod(paise_total, 100)
    text = f"Rupees {_words(rupees) or 'Zero'}"
    if paise:
        text += f" and {_below_hundred(paise)} Paise"
    return f"{text} Only"
