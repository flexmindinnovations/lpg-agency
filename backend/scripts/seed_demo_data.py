"""Seed a realistic demo dataset into any LPG environment.

Run against one database::

    LPG_SEED_DATABASE_URL="postgresql+asyncpg://lpg_admin:...@localhost:55432/lpg_dev" \
        uv run python scripts/seed_demo_data.py

With no `LPG_SEED_DATABASE_URL` it falls back to `LPG_MIGRATION_DATABASE_URL`,
then to the local dev DSN — and prints the resolved host either way, for the
same reason `migrations/env.py` does: a seed that silently lands on the wrong
database is worse than one that refuses to run.

**Every id is deterministic.** Ids come from `uuid5` over a stable natural key
(`branch:Hyderabad Central`, `customer:+919848012001`, …) rather than
`gen_random_uuid()`. Two consequences, both deliberate:

* The script is idempotent. Re-running inserts nothing new, because every row
  collides with itself on the primary key and is swallowed by
  `ON CONFLICT (id) DO NOTHING`. There is no "already seeded?" bookkeeping to
  get wrong, and a partially-failed run is fixed by running it again.
* The same logical record has the *same* id in `lpg_dev`, `lpg_test`,
  `lpg_uat` and Supabase. Comparing environments, or reproducing a UAT bug
  locally, becomes a matter of using the same id rather than hunting for the
  equivalent row.

Seeding connects as the migration/admin role, which is a superuser and so
bypasses RLS. That is required — the rows span tenants and there is no request
scope to set `app.current_tenant_id` from.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

_LOCAL_DEV_FALLBACK = (
    "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"
)

# Fixed namespace so ids are reproducible across runs *and* across machines.
# Changing this constant re-keys the entire dataset — don't.
_NS = uuid.UUID("6f1d2c3b-4a59-4e87-9b0c-1d2e3f405162")

TENANT_SLUG = "DEV123456"
DEMO_PASSWORD = "correct-horse-battery"  # noqa: S105 - dev-seed-only, not a real secret


def tenant_sid(key: str) -> uuid.UUID:
    """Stable id for the demo tenant row itself."""
    return uuid.uuid5(_NS, f"tenant:{key}")


def spread(key: str, modulo: int) -> int:
    """Deterministic small integer from `key`, for filler values.

    Derived from `uuid5` rather than `hash()`. Python randomises string hashing
    per process unless PYTHONHASHSEED is pinned, so `hash()` here would produce
    different house numbers and coordinates on every run and in every
    environment — the exact reproducibility this module is built around.
    """
    return uuid.uuid5(_NS, f"spread:{key}").int % modulo


# --- Dataset ---------------------------------------------------------------
# A single-city LPG distributor: three branches, a warehouse each, a delivery
# fleet, and a customer book spanning all four customer types.

BRANCHES = [
    ("Hyderabad Central", "Telangana"),
    ("Secunderabad North", "Telangana"),
    ("Gachibowli West", "Telangana"),
]

# (name, weight_kg) — the four cylinders an Indian distributor actually carries.
CYLINDER_TYPES = [
    ("Domestic 5kg", Decimal("5.0")),
    ("Domestic 14.2kg", Decimal("14.2")),
    ("Commercial 19kg", Decimal("19.0")),
    ("Commercial 47.5kg", Decimal("47.5")),
]

# (cylinder, customer_type, price)
PRICES = [
    ("Domestic 5kg", "domestic", Decimal("389.00")),
    ("Domestic 14.2kg", "domestic", Decimal("905.50")),
    ("Commercial 19kg", "commercial", Decimal("1755.00")),
    ("Commercial 19kg", "industrial", Decimal("1712.00")),
    ("Commercial 47.5kg", "commercial", Decimal("4310.00")),
    ("Commercial 47.5kg", "industrial", Decimal("4185.00")),
    ("Domestic 14.2kg", "government", Decimal("860.00")),
]

# (code, first, last, phone, role, branch)
EMPLOYEES = [
    ("EMP-1001", "Ravi", "Kumar", "+919848011001", "manager", "Hyderabad Central"),
    ("EMP-1002", "Sunita", "Reddy", "+919848011002", "dispatcher", "Hyderabad Central"),
    ("EMP-1003", "Imran", "Shaikh", "+919848011003", "driver", "Hyderabad Central"),
    ("EMP-1004", "Lakshmi", "Rao", "+919848011004", "accountant", "Hyderabad Central"),
    ("EMP-1005", "Vijay", "Naidu", "+919848011005", "driver", "Secunderabad North"),
    ("EMP-1006", "Prakash", "Menon", "+919848011006", "warehouse_staff", "Secunderabad North"),
    ("EMP-1007", "Anita", "Desai", "+919848011007", "driver", "Gachibowli West"),
    ("EMP-1008", "Farhan", "Ali", "+919848011008", "manager", "Gachibowli West"),
]

# (employee_code, licence, vehicle_reg, make, model, capacity)
FLEET = [
    ("EMP-1003", "TS-DL-2019-0043781", "TS07UB4412", "Tata", "Ace Gold", 80),
    ("EMP-1005", "TS-DL-2020-0091244", "TS08UC7781", "Mahindra", "Bolero Pik-Up", 120),
    ("EMP-1007", "TS-DL-2021-0117905", "TS09UA3320", "Ashok Leyland", "Dost+", 150),
]

# (name, phone, type, branch, area, pincode, status, kyc)
# `Customer.__init__` requires `contact_person` for customer_type=="commercial"
# specifically (not industrial/government) — the 3 seeded commercial
# customers below (name, keyed by phone).
COMMERCIAL_CONTACT_PERSONS = {
    "+919848012003": "Lakshmi Narayana",
    "+919848012005": "Farhan Qureshi",
    "+919848012009": "Divya Prasad",
}

CUSTOMERS = [
    ("Anand Krishnan", "+919848012001", "domestic", "Hyderabad Central",
     "Himayatnagar", "500029", "active", "verified"),
    ("Meena Iyer", "+919848012002", "domestic", "Hyderabad Central",
     "Basheerbagh", "500029", "active", "verified"),
    ("Sri Sai Tiffin Centre", "+919848012003", "commercial", "Hyderabad Central",
     "Koti", "500095", "active", "verified"),
    ("Deepa Varma", "+919848012004", "domestic", "Hyderabad Central",
     "Narayanguda", "500029", "active", "pending"),
    ("Hotel Golconda Grand", "+919848012005", "commercial", "Secunderabad North",
     "Paradise Circle", "500003", "active", "verified"),
    ("Rajesh Gupta", "+919848012006", "domestic", "Secunderabad North",
     "Trimulgherry", "500015", "active", "verified"),
    ("Bharat Ceramics Pvt Ltd", "+919848012007", "industrial", "Secunderabad North",
     "Balanagar", "500042", "active", "verified"),
    ("Kavitha Sharma", "+919848012008", "domestic", "Secunderabad North",
     "Marredpally", "500026", "onboarding", "pending"),
    ("Cyber Towers Canteen", "+919848012009", "commercial", "Gachibowli West",
     "HITEC City", "500081", "active", "verified"),
    ("Govt Primary School Gachibowli", "+919848012010", "government", "Gachibowli West",
     "Gachibowli", "500032", "active", "verified"),
    ("Suresh Babu", "+919848012011", "domestic", "Gachibowli West",
     "Kondapur", "500084", "active", "verified"),
    ("Nithya Menon", "+919848012012", "domestic", "Gachibowli West",
     "Madhapur", "500081", "inactive", "expired"),
]

# Login accounts, one per role worth exercising in the UI. `admin` is listed
# first because it also anchors tenant resolution — see `main`.
# (email, role, branch or None)
LOGIN_USERS = [
    ("admin@example.com", "agency_admin", "Hyderabad Central"),
    ("manager@example.com", "manager", "Hyderabad Central"),
    ("dispatcher@example.com", "dispatcher", "Hyderabad Central"),
    ("accountant@example.com", "accountant", "Hyderabad Central"),
    ("warehouse@example.com", "warehouse_staff", "Secunderabad North"),
    ("driver@example.com", "driver", "Hyderabad Central"),
]

# (customer phone, cylinder, qty, status, days_offset)
ORDERS = [
    ("+919848012001", "Domestic 14.2kg", 1, "delivered", -6),
    ("+919848012002", "Domestic 14.2kg", 1, "delivered", -5),
    ("+919848012003", "Commercial 19kg", 4, "delivered", -4),
    ("+919848012005", "Commercial 19kg", 6, "closed", -4),
    ("+919848012007", "Commercial 47.5kg", 3, "delivered", -3),
    ("+919848012009", "Commercial 19kg", 5, "out_for_delivery", 0),
    ("+919848012010", "Domestic 14.2kg", 8, "assigned", 0),
    ("+919848012011", "Domestic 14.2kg", 1, "confirmed", 0),
    ("+919848012006", "Domestic 14.2kg", 2, "booked", 1),
    ("+919848012004", "Domestic 5kg", 1, "booked", 1),
    ("+919848012001", "Domestic 5kg", 2, "cancelled", -2),
]


def _dsn() -> str:
    settings = get_settings()
    for source in ("LPG_SEED_DATABASE_URL", "LPG_MIGRATION_DATABASE_URL"):
        url = os.environ.get(source)
        if url:
            break
    else:
        url = str(settings.migration_database_url or "") or _LOCAL_DEV_FALLBACK
        source = "settings/fallback"
    parsed = urlsplit(url)
    print(f"[seed] target: {parsed.hostname}:{parsed.port or 5432}{parsed.path}  (from {source})")
    return url


async def main() -> None:
    dsn = _dsn()
    engine = create_async_engine(dsn)
    hasher = Argon2PasswordHasher(get_settings())
    now = datetime.now(UTC)

    async with engine.begin() as conn:

        async def ensure(
            table: str,
            *,
            match: str,
            columns: str,
            values: str,
            new_id: uuid.UUID,
            params: dict[str, object],
        ) -> uuid.UUID:
            """Return the id of the row matching `match`, inserting it if absent.

            Look-up-then-insert rather than `ON CONFLICT (id) DO NOTHING`,
            because a deterministic id only makes a row idempotent against
            *itself*. These databases already contain rows written by earlier
            seeds and by hand — `manager@example.com` existed in `lpg_dev` with
            a different id — and inserting a fresh id for an existing natural
            key hits the unique constraint instead of quietly doing nothing.

            It also sidesteps `ON CONFLICT`'s awkwardness with the constraints
            actually in play here: several are partial (`WHERE is_deleted =
            false`, `WHERE email IS NOT NULL`) and `tenant.price_list`'s is
            five columns with `NULLS NOT DISTINCT`. Inferring those from an
            `ON CONFLICT` target means restating each predicate exactly;
            matching on the natural key in a `WHERE` clause does not.

            Returns the *existing* id when one is found, so callers bind to
            whatever is really in the database rather than assuming their own
            generated id won.
            """
            found = (
                await conn.execute(text(f"SELECT id FROM {table} WHERE {match}"), params)  # noqa: S608 - fixed call-site literals, no user input
            ).scalar()
            if found is not None:
                return found
            await conn.execute(
                text(f"INSERT INTO {table} (id, {columns}) VALUES (:_new_id, {values})"),  # noqa: S608 - fixed call-site literals, no user input
                {**params, "_new_id": new_id},
            )
            return new_id

        # --- Tenant -------------------------------------------------------
        # Seed into whichever tenant `admin@example.com` belongs to, falling
        # back to the `DEV123456` slug `seed_dev_user.py` creates.
        #
        # Deliberately not a fixed slug. These environments turn out to hold
        # *two* tenants both named "Dev Agency Tenant" — `dev-tenant` and
        # `DEV123456`. On `lpg_dev` and Supabase the working logins sit in
        # `dev-tenant`; on `lpg_test` and `lpg_uat` there is no admin at all.
        # Seeding a fixed slug therefore filled a tenant nobody signs into and
        # left the one they do sign into empty — every row present and none of
        # it visible, since RLS scopes each read to the caller's tenant.
        # Anchoring on the admin account puts the data where it can be seen.
        tenant_id = (
            await conn.execute(
                text(
                    "SELECT tenant_id FROM identity.identity_user "
                    "WHERE email = 'admin@example.com'"
                )
            )
        ).scalar()
        if tenant_id is None:
            tenant_id = await ensure(
                "tenant.tenant",
                match="slug = :slug",
                columns="name, slug, status, country",
                values="'Dev Agency Tenant', :slug, 'active', 'IN'",
                new_id=tenant_sid(TENANT_SLUG),
                params={"slug": TENANT_SLUG},
            )
        tenant_slug = (
            await conn.execute(
                text("SELECT slug FROM tenant.tenant WHERE id = :id"), {"id": tenant_id}
            )
        ).scalar()
        print(f"[seed] tenant: {tenant_slug}  ({tenant_id})")
        p = {"t": tenant_id}

        def sid(kind: str, key: str) -> uuid.UUID:
            """Stable id for a logical record, namespaced by resolved tenant.

            Keyed on the tenant *id* rather than a constant so that seeding two
            different tenants in one database yields two disjoint id sets
            instead of primary-key collisions.
            """
            return uuid.uuid5(_NS, f"{tenant_id}:{kind}:{key}")

        # --- Branches and warehouses --------------------------------------
        # `branch` and `warehouse` carry no unique key beyond the PK, so the
        # deterministic id *is* the natural key for them.
        branch_ids: dict[str, uuid.UUID] = {}
        for name, region in BRANCHES:
            branch_ids[name] = await ensure(
                "tenant.branch",
                match="tenant_id = :t AND name = :name",
                columns="tenant_id, name, region",
                values=":t, :name, :region",
                new_id=sid("branch", name),
                params={**p, "name": name, "region": region},
            )
            await ensure(
                "tenant.warehouse",
                match="tenant_id = :t AND name = :name",
                columns="tenant_id, branch_id, name, address_line",
                values=":t, :b, :name, :addr",
                new_id=sid("warehouse", name),
                params={
                    **p,
                    "b": branch_ids[name],
                    "name": f"{name} Depot",
                    "addr": f"Plot 14, {region} Industrial Area, {name}",
                },
            )

        # --- Cylinder types and prices ------------------------------------
        cylinder_ids: dict[str, uuid.UUID] = {}
        for name, weight in CYLINDER_TYPES:
            cylinder_ids[name] = await ensure(
                "tenant.cylinder_type",
                match="tenant_id = :t AND name = :name AND is_deleted = false",
                columns="tenant_id, name, weight_kg, is_active",
                values=":t, :name, :w, true",
                new_id=sid("cylinder", name),
                params={**p, "name": name, "w": weight},
            )

        # This row's deterministic id (`sid("price", ...)`) is keyed only on
        # `(cyl, ctype)` — `effective_from` was never part of that key, so it
        # cannot also be part of the match clause below. It used to be
        # (`now - 90 days`), which meant a re-run on a later day matched on a
        # different `effective_from`, missed its own earlier row, and then
        # collided with it on the id-only primary key when re-inserting —
        # found while extending this script. Match on the real natural key
        # only; effective_from is still recorded for genuinely new rows.
        effective_from = date(2026, 1, 1)
        for cyl, ctype, price in PRICES:
            await ensure(
                "tenant.price_list",
                match=(
                    "tenant_id = :t AND cylinder_type_id = :c AND customer_type = :ct "
                    "AND branch_id IS NULL"
                ),
                columns="tenant_id, cylinder_type_id, customer_type, price, effective_from",
                values=":t, :c, :ct, :price, :eff",
                new_id=sid("price", f"{cyl}:{ctype}"),
                params={
                    **p,
                    "c": cylinder_ids[cyl],
                    "ct": ctype,
                    "price": price,
                    "eff": effective_from,
                },
            )

        # Cancellation fee policy — the key Phase 10 already recognised.
        # Same fix as price_list just above: this row's id is keyed only on
        # `config_key`, so effective_from cannot also gate the match.
        await ensure(
            "tenant.tenant_configuration",
            match="tenant_id = :t AND config_key = 'cancellation_fee_amount'",
            columns="tenant_id, config_key, config_value, effective_from",
            values=":t, 'cancellation_fee_amount', "
            "'{\"policy_type\": \"flat\", \"amount\": \"50.00\"}'::jsonb, :eff",
            new_id=sid("config", "cancellation_fee_amount"),
            params={**p, "eff": effective_from},
        )

        # --- Employees ----------------------------------------------------
        employee_ids: dict[str, uuid.UUID] = {}
        for code, first, last, phone, role, branch in EMPLOYEES:
            employee_ids[code] = await ensure(
                "tenant.employee",
                match="tenant_id = :t AND employee_code = :code",
                columns=(
                    "tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, email, role, status"
                ),
                values=":t, :b, :code, :f, :l, :ph, :em, :role, 'active'",
                new_id=sid("employee", code),
                params={
                    **p,
                    "b": branch_ids[branch],
                    "code": code,
                    "f": first,
                    "l": last,
                    "ph": phone,
                    "em": f"{first.lower()}.{last.lower()}@lpgdemo.in",
                    "role": role,
                },
            )

        # --- Login users ---------------------------------------------------
        # Hashing is the slow part of this script; five accounts keeps it brief.
        pw_hash = hasher.hash(DEMO_PASSWORD)
        for email, role, branch in LOGIN_USERS:
            user_id = await ensure(
                "identity.identity_user",
                match="email = :em",
                columns="tenant_id, email, password_hash, role",
                values=":t, :em, :pw, :role",
                new_id=sid("user", email),
                params={**p, "em": email, "pw": pw_hash, "role": role},
            )
            # `identity_user.email` is globally unique, not unique per tenant,
            # so a demo account stranded in some other tenant cannot simply be
            # re-created here. `lpg_dev` had `driver@example.com` sitting in
            # `DEV123456` while every other demo login lived in `dev-tenant`,
            # which would leave this user's `user_role` row pointing at one
            # tenant and the user at another. Move the account instead. Scoped
            # to the fixed `LOGIN_USERS` list — this never touches a real one.
            await conn.execute(
                text(
                    "UPDATE identity.identity_user SET tenant_id = :t, role = :role "
                    "WHERE id = :u AND tenant_id <> :t"
                ),
                {**p, "u": user_id, "role": role},
            )
            role_id = (
                await conn.execute(
                    text("SELECT id FROM identity.role WHERE code = :c"), {"c": role}
                )
            ).scalar()
            if role_id is not None:
                await ensure(
                    "identity.user_role",
                    match="user_id = :u AND role_id = :r",
                    columns="tenant_id, user_id, role_id",
                    values=":t, :u, :r",
                    new_id=sid("user_role", email),
                    params={**p, "u": user_id, "r": role_id},
                )
                # Mirror the role's permissions onto the user, matching what
                # `8c221c3e0a91` backfilled for pre-existing accounts.
                await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user_permission "
                        "(id, user_id, permission_id, created_at) "
                        "SELECT gen_random_uuid(), :u, rp.permission_id, now() "
                        "FROM identity.role_permission rp WHERE rp.role_id = :r "
                        "AND NOT EXISTS (SELECT 1 FROM identity.identity_user_permission e "
                        "WHERE e.user_id = :u AND e.permission_id = rp.permission_id)"
                    ),
                    {"u": user_id, "r": role_id},
                )
            _ = branch  # branch scoping is carried on the JWT, not this table

        # --- Drivers and vehicles ------------------------------------------
        driver_ids: dict[str, uuid.UUID] = {}
        vehicle_ids: dict[str, uuid.UUID] = {}
        for emp_code, licence, reg, make, model, capacity in FLEET:
            branch = next(b for c, *_, b in EMPLOYEES if c == emp_code)
            driver_ids[emp_code] = await ensure(
                "delivery.driver",
                match="tenant_id = :t AND employee_id = :e",
                columns=(
                    "tenant_id, branch_id, employee_id, license_number, "
                    "license_expiry_date, status"
                ),
                values=":t, :b, :e, :lic, :exp, 'active'",
                new_id=sid("driver", emp_code),
                params={
                    **p,
                    "b": branch_ids[branch],
                    "e": employee_ids[emp_code],
                    "lic": licence,
                    "exp": date(2028, 6, 30),
                },
            )
            vehicle_ids[reg] = await ensure(
                "delivery.vehicle",
                match="tenant_id = :t AND registration_number = :reg",
                columns=(
                    "tenant_id, branch_id, registration_number, make, model, "
                    "ownership_type, capacity_units, status"
                ),
                values=":t, :b, :reg, :make, :model, 'owned', :cap, 'active'",
                new_id=sid("vehicle", reg),
                params={
                    **p,
                    "b": branch_ids[branch],
                    "reg": reg,
                    "make": make,
                    "model": model,
                    "cap": capacity,
                },
            )

        # --- Inventory ------------------------------------------------------
        # A location per warehouse and per vehicle, then opening balances.
        async def _location(kind: str, ref_key: str, ref_id: uuid.UUID) -> uuid.UUID:
            return await ensure(
                "inventory.inventory_location",
                match="tenant_id = :t AND location_type = :kind AND location_ref_id = :ref",
                columns="tenant_id, location_type, location_ref_id",
                values=":t, :kind, :ref",
                new_id=sid("location", f"{kind}:{ref_key}"),
                params={**p, "kind": kind, "ref": ref_id},
            )

        async def _balance(loc_id: uuid.UUID, cyl: str, status: str, qty: int) -> None:
            await ensure(
                "inventory.inventory_balance",
                match=(
                    "inventory_location_id = :loc AND cylinder_type_id = :cyl AND status = :st"
                ),
                columns=(
                    "tenant_id, inventory_location_id, cylinder_type_id, status, quantity"
                ),
                values=":t, :loc, :cyl, :st, :q",
                new_id=sid("balance", f"{loc_id}:{cyl}:{status}"),
                params={**p, "loc": loc_id, "cyl": cylinder_ids[cyl], "st": status, "q": qty},
            )

        # Warehouses hold the bulk; heavier cylinders stock more thinly.
        warehouse_stock = {
            "Domestic 5kg": (120, 40),
            "Domestic 14.2kg": (450, 160),
            "Commercial 19kg": (180, 70),
            "Commercial 47.5kg": (60, 25),
        }
        for branch_name, _ in BRANCHES:
            warehouse_id = (
                await conn.execute(
                    text("SELECT id FROM tenant.warehouse WHERE tenant_id = :t AND name = :n"),
                    {**p, "n": f"{branch_name} Depot"},
                )
            ).scalar_one()
            loc = await _location("warehouse", branch_name, warehouse_id)
            for cyl, (filled, empty) in warehouse_stock.items():
                await _balance(loc, cyl, "filled", filled)
                await _balance(loc, cyl, "empty", empty)
            await _balance(loc, "Domestic 14.2kg", "damaged", 3)

        # Vehicles carry a day's load.
        for _, _, reg, _, _, _ in FLEET:
            loc = await _location("vehicle", reg, vehicle_ids[reg])
            await _balance(loc, "Domestic 14.2kg", "filled", 30)
            await _balance(loc, "Commercial 19kg", "filled", 10)
            await _balance(loc, "Domestic 14.2kg", "empty", 12)

        # --- Customers and addresses ----------------------------------------
        customer_ids: dict[str, uuid.UUID] = {}
        address_ids: dict[str, uuid.UUID] = {}
        for idx, (name, phone, ctype, branch, area, pincode, status, kyc) in enumerate(CUSTOMERS):
            # `Customer.__init__` requires a `consumer_number` for every
            # status except onboarding/pending_approval — written directly
            # here (`CN-NNNNNN`, matching `CustomerNumberSequenceRepository`'s
            # own format) rather than through that sequence service, for the
            # same reason Orders below are written directly. Never having set
            # this broke `GET /customers` outright for every seeded customer
            # past onboarding, the same way the address_type bug just above
            # did — found the same way, by that endpoint 409ing.
            consumer_number = (
                None if status in ("onboarding", "pending_approval") else f"CN-{idx + 1:06d}"
            )
            # Same story as consumer_number — commercial customers need a
            # contact_person, this seed never set one.
            contact_person = COMMERCIAL_CONTACT_PERSONS.get(phone) if ctype == "commercial" else None
            cust_id = await ensure(
                "customer.customer",
                match="tenant_id = :t AND phone_number = :ph",
                columns=(
                    "tenant_id, branch_id, full_name, phone_number, "
                    "customer_type, kyc_status, status, consumer_number, contact_person"
                ),
                values=":t, :b, :n, :ph, :ct, :kyc, :st, :cn, :cp",
                new_id=sid("customer", phone),
                params={
                    **p,
                    "b": branch_ids[branch],
                    "n": name,
                    "ph": phone,
                    "ct": ctype,
                    "kyc": kyc,
                    "st": status,
                    "cn": consumer_number,
                    "cp": contact_person,
                },
            )
            customer_ids[phone] = cust_id
            address_ids[phone] = await ensure(
                "customer.customer_address",
                # The unique index is partial (one primary per undeleted
                # customer), so match on the same shape it constrains.
                match="customer_id = :c AND is_primary = true AND is_deleted = false",
                columns=(
                    "tenant_id, customer_id, line_1, area, city, district, state, "
                    "pincode, address_type, is_primary, latitude, longitude"
                ),
                values=(
                    ":t, :c, :l1, :area, 'Hyderabad', 'Hyderabad', 'Telangana', "
                    ":pin, :atype, true, :lat, :lng"
                ),
                new_id=sid("address", phone),
                params={
                    **p,
                    "c": cust_id,
                    "l1": f"{spread(phone, 900) + 1}-{spread(name, 90) + 10}, {area}",
                    "area": area,
                    "pin": pincode,
                    # `domain/customer/customer.py`'s `CustomerAddress` only
                    # accepts delivery/billing/both — "residential"/
                    # "commercial" (this field's old values) were never valid
                    # and broke `GET /customers` outright the moment it tried
                    # to reconstruct any of these rows into a domain object.
                    "atype": "delivery" if ctype == "domestic" else "both",
                    # Scattered around Hyderabad so the dispatch map has spread.
                    "lat": Decimal("17.3850") + Decimal(spread(phone, 500)) / Decimal(10000),
                    "lng": Decimal("78.4867") + Decimal(spread(area, 500)) / Decimal(10000),
                },
            )

        # --- Orders -----------------------------------------------------------
        # Written directly rather than driven through the state machine: this
        # is display data for the queue, dashboard and reports, and replaying
        # ten aggregates through eleven transitions here would duplicate the
        # use-case layer without testing it. Inventory balances above are
        # therefore *opening* stock and are not adjusted per order.
        admin_id = (
            await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE email = 'admin@example.com'")
            )
        ).scalar() or sid("user", "manager@example.com")

        price_by_key = {(c, ct): pr for c, ct, pr in PRICES}
        order_ids: dict[str, uuid.UUID] = {}
        for idx, (phone, cyl, qty, status, offset) in enumerate(ORDERS):
            cust = next(c for c in CUSTOMERS if c[1] == phone)
            ctype, branch = cust[2], cust[3]
            unit_price = price_by_key.get((cyl, ctype)) or Decimal("905.50")
            priced = status not in {"booked", "cancelled"}
            delivered = status in {"delivered", "closed"}
            # `orders.order` has no unique constraint, so match on the triple
            # that is unique *within this dataset* — one order per customer per
            # status — rather than on the id.
            #
            # Matching on id looked equivalent and was not: the id is derived
            # from the tenant, so when tenant resolution changed, every probe
            # missed and a second full set of orders was inserted. Every other
            # entity here survived that change untouched, because each was
            # matched on a real natural key (branch name, customer phone,
            # vehicle registration) that does not move when the id scheme does.
            # A natural key that is independent of how ids are generated is the
            # only kind that makes a seed genuinely re-runnable.
            order_id = await ensure(
                'orders."order"',
                match="tenant_id = :t AND customer_id = :c AND status = :st",
                columns=(
                    "tenant_id, branch_id, customer_id, address_id, delivery_address_line, "
                    "status, booking_source, payment_method_preference, requested_date, "
                    "total_amount"
                ),
                values=":t, :b, :c, :a, :addr, :st, :src, :pay, :req, :total",
                new_id=sid("order", f"{phone}:{idx}"),
                params={
                    **p,
                    "b": branch_ids[branch],
                    "c": customer_ids[phone],
                    "a": address_ids[phone],
                    "addr": f"{cust[4]}, Hyderabad, Telangana {cust[5]}",
                    "st": status,
                    "src": ("mobile_app", "staff", "phone", "whatsapp")[idx % 4],
                    "pay": "upi" if ctype == "domestic" else "credit",
                    "req": now + timedelta(days=offset),
                    "total": (unit_price * qty) if priced else None,
                },
            )
            order_ids[f"{phone}:{idx}"] = order_id
            await ensure(
                "orders.order_line",
                match="order_id = :o AND cylinder_type_id = :cyl",
                columns=(
                    "order_id, cylinder_type_id, quantity_ordered, quantity_delivered, "
                    "quantity_collected_empty, unit_price"
                ),
                values=":o, :cyl, :q, :qd, :qe, :price",
                new_id=sid("order_line", f"{phone}:{idx}"),
                params={
                    "o": order_id,
                    "cyl": cylinder_ids[cyl],
                    "q": qty,
                    "qd": qty if delivered else 0,
                    "qe": qty if delivered else 0,
                    "price": unit_price if priced else None,
                },
            )
            await ensure(
                "orders.order_status_history",
                match="order_id = :o AND to_status = :st",
                columns="order_id, from_status, to_status, changed_by, changed_at",
                values=":o, NULL, :st, :by, :at",
                new_id=sid("order_history", f"{phone}:{idx}"),
                params={
                    "o": order_id,
                    "st": status,
                    "by": admin_id,
                    "at": now + timedelta(days=offset),
                },
            )

        # --- Invoices -----------------------------------------------------
        # Written directly, same reasoning as Orders above — the delivered/
        # closed subset of ORDERS is what `GenerateInvoiceForOrderUseCase`
        # would have produced. Backs `rpt.vw_daily_sales` (live view) and
        # `rpt.mv_gst_filing_period` (materialized, refreshed below).
        gst_rate_by_customer_type = {"domestic": Decimal("0.05")}  # else 18%
        invoice_ids: dict[str, uuid.UUID] = {}
        for idx, (phone, cyl, qty, status, offset) in enumerate(ORDERS):
            if status not in {"delivered", "closed"}:
                continue
            cust = next(c for c in CUSTOMERS if c[1] == phone)
            ctype = cust[2]
            unit_price = price_by_key.get((cyl, ctype)) or Decimal("905.50")
            subtotal = unit_price * qty
            gst_rate = gst_rate_by_customer_type.get(ctype, Decimal("0.18"))
            tax_amount = (subtotal * gst_rate).quantize(Decimal("0.01"))
            total_amount = subtotal + tax_amount
            order_key = f"{phone}:{idx}"
            invoice_id = await ensure(
                "accounting.invoice",
                match="order_id = :o",
                columns=(
                    "tenant_id, customer_id, order_id, status, subtotal, tax_amount, "
                    "total_amount, issued_at"
                ),
                values=":t, :c, :o, :st, :sub, :tax, :total, :at",
                new_id=sid("invoice", order_key),
                params={
                    **p,
                    "c": customer_ids[phone],
                    "o": order_ids[order_key],
                    # Older deliveries have had time to be paid; the rest are
                    # still outstanding — a plausible spread, not a fake one.
                    "st": "paid" if offset <= -5 else "issued",
                    "sub": subtotal,
                    "tax": tax_amount,
                    "total": total_amount,
                    "at": now + timedelta(days=offset),
                },
            )
            invoice_ids[order_key] = invoice_id
            await ensure(
                "accounting.invoice_line",
                match="invoice_id = :i AND cylinder_type_id = :cyl",
                columns=(
                    "invoice_id, cylinder_type_id, quantity, unit_price, subtotal, "
                    "tax_amount, total_amount"
                ),
                values=":i, :cyl, :q, :price, :sub, :tax, :total",
                new_id=sid("invoice_line", order_key),
                params={
                    "i": invoice_id,
                    "cyl": cylinder_ids[cyl],
                    "q": qty,
                    "price": unit_price,
                    "sub": subtotal,
                    "tax": tax_amount,
                    "total": total_amount,
                },
            )

        # --- Driver routes --------------------------------------------------
        # Backs `rpt.mv_driver_performance_daily` (materialized, refreshed
        # below). One route per driver, referencing real orders as stops —
        # the Gachibowli route deliberately mixes in two still-pending stops
        # rather than showing every driver at a fake 100%.
        DRIVER_ROUTES: list[tuple[str, str, int, str, list[tuple[str, str]]]] = [
            (
                "EMP-1003", "TS07UB4412", -6, "completed",
                [("+919848012001:0", "delivered"),
                 ("+919848012002:1", "delivered"),
                 ("+919848012003:2", "delivered")],
            ),
            (
                "EMP-1005", "TS08UC7781", -4, "completed",
                [("+919848012005:3", "delivered"),
                 ("+919848012007:4", "delivered")],
            ),
            (
                "EMP-1007", "TS09UA3320", -1, "in_progress",
                [("+919848012009:5", "delivered"),
                 ("+919848012010:6", "pending"),
                 ("+919848012011:7", "pending")],
            ),
        ]
        for emp_code, reg, offset, route_status, stops in DRIVER_ROUTES:
            route_key = f"{emp_code}:{offset}"
            route_id = await ensure(
                "delivery.route",
                match="tenant_id = :t AND driver_id = :d AND route_date = :rd",
                columns="tenant_id, branch_id, driver_id, vehicle_id, route_date, status",
                values=":t, :b, :d, :v, :rd, :st",
                new_id=sid("route", route_key),
                params={
                    **p,
                    "b": branch_ids[next(b for c, *_, b in EMPLOYEES if c == emp_code)],
                    "d": driver_ids[emp_code],
                    "v": vehicle_ids[reg],
                    "rd": now + timedelta(days=offset),
                    "st": route_status,
                },
            )
            for seq, (order_key, stop_status) in enumerate(stops, start=1):
                await ensure(
                    "delivery.route_stop",
                    match="route_id = :r AND order_id = :o",
                    columns="route_id, order_id, sequence_number, status",
                    values=":r, :o, :seq, :st",
                    new_id=sid("route_stop", f"{route_key}:{order_key}"),
                    params={
                        "r": route_id,
                        "o": order_ids[order_key],
                        "seq": seq,
                        "st": stop_status,
                    },
                )

        # --- Cylinder ledger deliveries ---------------------------------------
        # Backs `rpt.mv_customer_consumption` (materialized, refreshed below)
        # — it needs at least two `delivery` transactions per customer to
        # compute a refill interval (`3dd09c061286` fixed the view to key on
        # the real `delivery` transaction type instead of a phantom
        # `exchange` one the domain layer never actually writes). Spread
        # ~monthly, well outside the reports' 30-day sales window on purpose:
        # consumption history is meant to be long-range.
        CONSUMPTION = [
            # (phone, cylinder, day_offsets)
            ("+919848012001", "Domestic 14.2kg", (-95, -65, -35, -8)),
            ("+919848012002", "Domestic 14.2kg", (-80, -50, -22)),
            ("+919848012003", "Commercial 19kg", (-70, -42, -18)),
        ]
        for phone, cyl, offsets in CONSUMPTION:
            ledger_id = await ensure(
                "cylinder_ledger.cylinder_ledger",
                match="tenant_id = :t AND customer_id = :c",
                columns="tenant_id, customer_id",
                values=":t, :c",
                new_id=sid("cylinder_ledger", phone),
                params={**p, "c": customer_ids[phone]},
            )
            for offset in offsets:
                await ensure(
                    "cylinder_ledger.ledger_transaction",
                    match="cylinder_ledger_id = :l AND performed_at = :at",
                    columns=(
                        "tenant_id, cylinder_ledger_id, cylinder_type_id, "
                        "transaction_type, quantity, reason, performed_by, performed_at"
                    ),
                    values=":t, :l, :cyl, 'delivery', 1, 'Refill delivery', :by, :at",
                    new_id=sid("ledger_txn", f"{phone}:{offset}"),
                    params={
                        **p,
                        "l": ledger_id,
                        "cyl": cylinder_ids[cyl],
                        "by": admin_id,
                        "at": now + timedelta(days=offset),
                    },
                )

        # Materialized views don't see the rows above until refreshed.
        for view in (
            "rpt.mv_gst_filing_period",
            "rpt.mv_customer_consumption",
            "rpt.mv_driver_performance_daily",
        ):
            await conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))  # noqa: S608 - fixed literal, no user input

        # --- Summary ---------------------------------------------------------
        counts = await conn.execute(
            text("""
                SELECT
                  (SELECT count(*) FROM tenant.branch)              AS branches,
                  (SELECT count(*) FROM tenant.warehouse)           AS warehouses,
                  (SELECT count(*) FROM tenant.cylinder_type)       AS cylinder_types,
                  (SELECT count(*) FROM tenant.price_list)          AS prices,
                  (SELECT count(*) FROM tenant.employee)            AS employees,
                  (SELECT count(*) FROM delivery.driver)            AS drivers,
                  (SELECT count(*) FROM delivery.vehicle)           AS vehicles,
                  (SELECT count(*) FROM customer.customer)          AS customers,
                  (SELECT count(*) FROM inventory.inventory_balance) AS balances,
                  (SELECT count(*) FROM orders."order")             AS orders,
                  (SELECT count(*) FROM accounting.invoice)         AS invoices,
                  (SELECT count(*) FROM delivery.route)             AS routes,
                  (SELECT count(*) FROM delivery.route_stop)        AS route_stops,
                  (SELECT count(*) FROM cylinder_ledger.ledger_transaction) AS ledger_transactions
            """)
        )
        row = counts.mappings().one()

    await engine.dispose()

    print("[seed] done. row counts:")
    for key, value in row.items():
        print(f"         {key:<16} {value}")
    print(f"\n[seed] demo logins (password: {DEMO_PASSWORD}):")
    for email, role, _ in LOGIN_USERS:
        print(f"         {email:<28} {role}")


if __name__ == "__main__":
    asyncio.run(main())
