"""The modules a super admin switches on for an agency.

A fixed catalog in code (the same choice `PLAN_TIER_FEATURE_CATALOG` makes):
adding a module is a code change and never needs a migration for the catalog
itself. **Every module is off by default**: an agency can use a module only
while it has an `enabled` row for it, so a newly created agency starts with
nothing but the always-on basics (Home, Notifications, Settings and the
Administration screens: branches, godowns, cylinder types, pricing, users,
employees, audit log) until a super admin switches modules on.

A module that is off is hidden in the dashboard and its API refuses calls
with `MODULE_DISABLED` (`require_module_access`, which maps the request path to
its module through `module_for_path`, so a route cannot be forgotten by adding
it to a router).

Modules can depend on others (`requires`): a module can only be switched on
while the modules it needs are on, and a module can only be switched off while
no switched-on module needs it. The catalog is listed dependencies first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToggleableModule:
    key: str
    label: str
    description: str
    #: Heading the module is listed under in the Platform Console.
    group: str
    #: Keys of modules that must be on for this one to be on.
    requires: tuple[str, ...] = ()
    #: Regexes over the API path below `/api/v1`; a request matching any of
    #: them belongs to this module (the first match in catalog order wins).
    path_patterns: tuple[str, ...] = ()


TOGGLEABLE_MODULES: tuple[ToggleableModule, ...] = (
    # -- Operations ----------------------------------------------------------------
    ToggleableModule(
        "customers",
        "Customers",
        "Customer records, onboarding, KYC and cylinder ledger.",
        "Operations",
        path_patterns=(r"^/customers(/|$)",),
    ),
    ToggleableModule(
        "inventory",
        "Inventory",
        "Godown and vehicle stock, goods receipts, transfers and reconciliation.",
        "Logistics",
        path_patterns=(
            r"^/inventory(/|-locations/|$)",
            r"^/reconciliation-records(/|$)",
            r"^/goods-receipt-notes(/|$)",
            r"^/warehouses/[^/]+/(goods-receipt-notes|omc-returns)(/|$)",
            r"^/vehicles/[^/]+/(collections|deliveries)(/|$)",
        ),
    ),
    ToggleableModule(
        "orders",
        "Orders",
        "Order booking, confirmation, delivery follow-up and proof of delivery.",
        "Operations",
        # Only cylinders in stock can be booked, and stock is recorded in Inventory.
        requires=("customers", "inventory"),
        path_patterns=(r"^/orders(/|$)",),
    ),
    ToggleableModule(
        "complaints",
        "Complaints",
        "Customer complaints, assignment and resolution.",
        "Operations",
        path_patterns=(r"^/complaints(/|$)",),
    ),
    # -- Logistics -----------------------------------------------------------------
    ToggleableModule(
        "drivers",
        "Drivers",
        "Driver records, licences and assignments.",
        "Logistics",
        path_patterns=(r"^/drivers(/|$)",),
    ),
    ToggleableModule(
        "vehicles",
        "Vehicles",
        "Vehicle records, papers and status.",
        "Logistics",
        path_patterns=(r"^/vehicles(?!/[^/]+/(?:collections|deliveries)(?:/|$))(?:/|$)",),
    ),
    ToggleableModule(
        "dispatch",
        "Dispatch",
        "Delivery routes and trips.",
        "Logistics",
        requires=("orders", "drivers", "vehicles"),
        path_patterns=(r"^/routes(/|$)",),
    ),
    ToggleableModule(
        "scales",
        "Scales",
        "Weighing scales and their calibration certificates.",
        "Logistics",
        path_patterns=(r"^/scales(/|$)",),
    ),
    ToggleableModule(
        "cylinder_units",
        "Cylinder Units",
        "Individual cylinder identity, tracking and history.",
        "Logistics",
        path_patterns=(r"^/cylinder-units(/|$)",),
    ),
    ToggleableModule(
        "compliance_calendar",
        "Compliance Calendar",
        "Licence and certificate expiry tracking.",
        "Logistics",
        path_patterns=(r"^/compliance-documents(/|$)",),
    ),
    # -- Accounting ----------------------------------------------------------------
    ToggleableModule(
        "invoices",
        "Invoices",
        "Invoices, printing and payment status.",
        "Accounting",
        requires=("orders",),
        path_patterns=(r"^/invoices(/|$)", r"^/print-jobs(/|$)"),
    ),
    ToggleableModule(
        "cash_handovers",
        "Cash Handovers",
        "Driver cash handover submission and review.",
        "Accounting",
        requires=("drivers",),
        path_patterns=(r"^/cash-handovers(/|$)",),
    ),
    # -- Insights ------------------------------------------------------------------
    ToggleableModule(
        "reports",
        "Reports",
        "Sales, stock and compliance reports and exports.",
        "Insights",
        path_patterns=(r"^/reporting(/|$)", r"^/tdt-rating(/|$)"),
    ),
    ToggleableModule(
        "ai_command_center",
        "AI Command Center",
        "Ask operational questions in plain language.",
        "Insights",
        path_patterns=(r"^/ai(/|$)",),
    ),
)

MODULE_KEYS: frozenset[str] = frozenset(module.key for module in TOGGLEABLE_MODULES)

_BY_KEY: dict[str, ToggleableModule] = {module.key: module for module in TOGGLEABLE_MODULES}

_COMPILED_PATHS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), module.key)
    for module in TOGGLEABLE_MODULES
    for pattern in module.path_patterns
)


def is_module_key(key: str) -> bool:
    return key in MODULE_KEYS


def module_for_path(path: str) -> str | None:
    """The module an API path (below `/api/v1`) belongs to, or `None` for the
    always-on parts of the product."""
    for pattern, key in _COMPILED_PATHS:
        if pattern.search(path):
            return key
    return None


def modules_needing(key: str) -> tuple[str, ...]:
    """Keys of the modules that list `key` in `requires`."""
    return tuple(m.key for m in TOGGLEABLE_MODULES if key in m.requires)


def requirements_of(key: str) -> tuple[str, ...]:
    return _BY_KEY[key].requires
