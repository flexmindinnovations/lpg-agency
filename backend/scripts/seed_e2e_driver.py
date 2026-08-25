"""Seeds a driver login usable for the Deliver step of the order-to-delivery
E2E workflow (`frontend/apps/dashboard-e2e/src/order-to-delivery-workflow.spec.ts`
and `planning/order-to-delivery-e2e-checklist.md`).

Why this exists: `orders:deliver` is driver-role-only, and the backend
additionally checks the order's assigned driver's `identity_user_id` matches
the caller (`_require_own_driver_order`, `api/v1/routers/order.py`) — but
`delivery.driver` rows created by ad-hoc/demo seeding often leave
`identity_user_id` NULL (no login can ever pass that check for them), and
there's no API to link one after the fact (`identity_user_id` is only
settable at driver-registration time). This script creates one from scratch,
linked correctly, so the Deliver step is actually reachable end to end.

Same pattern as `seed_dev_user.py` (raw SQL via the migration/admin DSN,
bypassing RLS) — idempotent, safe to re-run.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

EMAIL = "e2e.driver@example.com"
PASSWORD = "correct-horse-battery"  # noqa: S105 - dev-seed-only, not a real secret
EMPLOYEE_CODE = "EMP-E2E-DRIVER"
PHONE_NUMBER = "+919999900099"
LICENSE_NUMBER = "E2E-TEST-LICENSE"
# Must be a branch with at least one active vehicle — Hyderabad Central has
# TS07UB4412 in the current dev database.
BRANCH_NAME = "Hyderabad Central"


async def main() -> None:
    settings = get_settings()
    dsn = settings.migration_database_url
    if not dsn:
        print("LPG_MIGRATION_DATABASE_URL not set. Trying default dev admin DSN...")
        dsn = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"

    engine = create_async_engine(str(dsn))
    hasher = Argon2PasswordHasher(settings)

    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text("SELECT tenant_id FROM identity.identity_user WHERE email = 'admin@example.com'")
            )
        ).scalar()
        if tenant_id is None:
            print("admin@example.com not found — run seed_dev_user.py first.")
            return

        role_id = (
            await conn.execute(text("SELECT id FROM identity.role WHERE code = 'driver'"))
        ).scalar()
        if role_id is None:
            print("Error: role 'driver' not found. Make sure migrations are run.")
            return

        branch_id = (
            await conn.execute(
                text("SELECT id FROM tenant.branch WHERE tenant_id = :tenant_id AND name = :name"),
                {"tenant_id": tenant_id, "name": BRANCH_NAME},
            )
        ).scalar()
        if branch_id is None:
            print(f"Error: branch {BRANCH_NAME!r} not found for this tenant.")
            return

        user_id = (
            await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE email = :email"), {"email": EMAIL}
            )
        ).scalar()
        if user_id is None:
            print(f"Creating identity_user {EMAIL!r}...")
            pw_hash = hasher.hash(PASSWORD)
            user_id = (
                await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user "
                        "(id, tenant_id, email, password_hash, role) "
                        "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, 'driver') "
                        "RETURNING id"
                    ),
                    {"tenant_id": tenant_id, "email": EMAIL, "password_hash": pw_hash},
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO identity.user_role (id, tenant_id, user_id, role_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, :user_id, :role_id)"
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "role_id": role_id},
            )
        else:
            print(f"identity_user {EMAIL!r} already exists.")

        # `SqlAlchemyIdentityUserRepository.add()` materializes a user's
        # `role_permission` set into `identity_user_permission` at creation
        # time (`8c221c3e0a91` moved permission resolution from role-based
        # to per-user — there is no read-time fallback to `role_permission`,
        # see that repository's `add()` docstring). This script inserts
        # `identity_user` directly, bypassing that, so the driver would
        # otherwise mint a JWT with an empty `scope` — do it here too,
        # idempotently, so re-running this script also repairs a
        # previously-empty permission set.
        await conn.execute(
            text("DELETE FROM identity.identity_user_permission WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = 'driver'"
            ),
            {"user_id": user_id},
        )

        employee_id = (
            await conn.execute(
                text(
                    "SELECT id FROM tenant.employee WHERE tenant_id = :tenant_id AND employee_code = :code"
                ),
                {"tenant_id": tenant_id, "code": EMPLOYEE_CODE},
            )
        ).scalar()
        if employee_id is None:
            print(f"Creating employee {EMPLOYEE_CODE!r}...")
            employee_id = (
                await conn.execute(
                    text(
                        "INSERT INTO tenant.employee "
                        "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                        "phone_number, email, role, status) "
                        "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :code, 'E2E', 'Driver', "
                        ":phone, :email, 'driver', 'active') "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "branch_id": branch_id,
                        "code": EMPLOYEE_CODE,
                        "phone": PHONE_NUMBER,
                        "email": EMAIL,
                    },
                )
            ).scalar_one()
        else:
            print(f"employee {EMPLOYEE_CODE!r} already exists.")

        driver_id = (
            await conn.execute(
                text("SELECT id FROM delivery.driver WHERE tenant_id = :tenant_id AND employee_id = :emp"),
                {"tenant_id": tenant_id, "emp": employee_id},
            )
        ).scalar()
        if driver_id is None:
            print("Creating driver profile linked to the identity_user above...")
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(tenant_id, branch_id, identity_user_id, employee_id, license_number, status) "
                    "VALUES (:tenant_id, :branch_id, :identity_user_id, :employee_id, :license, 'active')"
                ),
                {
                    "tenant_id": tenant_id,
                    "branch_id": branch_id,
                    "identity_user_id": user_id,
                    "employee_id": employee_id,
                    "license": LICENSE_NUMBER,
                },
            )
        else:
            # Existing driver profile (e.g. re-run after a partial failure) —
            # make sure the link is actually there.
            await conn.execute(
                text("UPDATE delivery.driver SET identity_user_id = :user_id WHERE id = :driver_id"),
                {"user_id": user_id, "driver_id": driver_id},
            )
            print("driver profile already existed — ensured identity_user_id link.")

    await engine.dispose()
    print("\nDone.")
    print(f"Login Email:    {EMAIL}")
    print(f"Login Password: {PASSWORD}")
    print(f"Branch:         {BRANCH_NAME}")
    print("Assign an order to this driver (employee code EMP-E2E-DRIVER) to deliver it as this user.")


if __name__ == "__main__":
    asyncio.run(main())
