"""Modules a super admin can switch off for an agency.

A fixed catalog in code (the same choice `PLAN_TIER_FEATURE_CATALOG` makes):
adding a module is a code change and never needs a migration. Every module
is **on by default**; an agency only has a row when a super admin has
switched something. A module that is off is hidden in the dashboard and its
API refuses calls (`require_module`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToggleableModule:
    key: str
    label: str
    description: str


TOGGLEABLE_MODULES: tuple[ToggleableModule, ...] = (
    ToggleableModule(
        "ai_command_center",
        "AI Command Center",
        "Ask operational questions in plain language.",
    ),
    ToggleableModule(
        "scales",
        "Scales",
        "Weighing scales and their calibration certificates.",
    ),
    ToggleableModule(
        "cylinder_units",
        "Cylinder Units",
        "Individual cylinder identity, tracking and history.",
    ),
    ToggleableModule(
        "reports",
        "Reports",
        "Sales, stock and compliance reports and exports.",
    ),
    ToggleableModule(
        "complaints",
        "Complaints",
        "Customer complaints, assignment and resolution.",
    ),
    ToggleableModule(
        "cash_handovers",
        "Cash Handovers",
        "Driver cash handover submission and review.",
    ),
)

MODULE_KEYS: frozenset[str] = frozenset(module.key for module in TOGGLEABLE_MODULES)


def is_module_key(key: str) -> bool:
    return key in MODULE_KEYS
