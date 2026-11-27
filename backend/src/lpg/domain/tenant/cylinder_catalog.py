"""The cylinder sizes an agency can deal in (ADR-079).

These are the sizes IndianOil and HPCL publish. An agency picks from this
list and cannot type its own name or weight. Adding a size is a code change.

A cylinder type is "on the list" when its name and weight both match an
entry, so records typed before the list existed need no migration. Changing
an entry's name would take existing records off the list.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: Household supply.
DOMESTIC = "domestic"
#: Commercial and industrial supply.
COMMERCIAL = "commercial"


@dataclass(frozen=True, slots=True)
class CylinderSize:
    code: str
    name: str
    category: str
    weight_kg: Decimal


def _size(code: str, name: str, category: str, weight_kg: str) -> CylinderSize:
    return CylinderSize(code, name, category, Decimal(weight_kg))


CYLINDER_SIZES: tuple[CylinderSize, ...] = (
    _size("domestic_5", "5 kg Domestic", DOMESTIC, "5"),
    _size("domestic_10_composite", "10 kg Domestic Composite", DOMESTIC, "10"),
    _size("domestic_14_2", "14.2 kg Domestic", DOMESTIC, "14.2"),
    _size("commercial_2", "2 kg Commercial", COMMERCIAL, "2"),
    _size("commercial_5_ftl", "5 kg Free Trade (FTL)", COMMERCIAL, "5"),
    _size("commercial_19", "19 kg Commercial", COMMERCIAL, "19"),
    _size("commercial_35", "35 kg Commercial", COMMERCIAL, "35"),
    _size("commercial_47_5", "47.5 kg Commercial", COMMERCIAL, "47.5"),
    _size("commercial_425", "425 kg Commercial", COMMERCIAL, "425"),
)


def size_by_code(code: str) -> CylinderSize | None:
    return next((size for size in CYLINDER_SIZES if size.code == code), None)


def size_matching(name: str, weight_kg: Decimal) -> CylinderSize | None:
    return next(
        (size for size in CYLINDER_SIZES if size.name == name and size.weight_kg == weight_kg),
        None,
    )
