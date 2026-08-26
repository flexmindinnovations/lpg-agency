"""Seeds a customer login usable for testing/verifying customer-role backend
endpoints and, eventually, the customer_app mobile rebuild
(`planning/order-workflows-and-notifications.md`'s "Customers have no
interface at all yet" gap, and the customer_app rebuild plan).

Why this exists: every demo `customer.customer` row in the seeded dev
tenant has `identity_user_id = NULL` (confirmed by querying directly) --
same problem `seed_e2e_driver.py` solved for the driver role. No customer
login can reach any endpoint gated on being the record's own owner
(cylinder ledger, KYC, invoices, complaints -- the endpoints Phase 0 of
the customer_app rebuild plan touches) without one. `customer_id` is its
own independently-generated primary key, never equal to
`identity_user_id` (confirmed in `RegisterCustomerUseCase`) -- the two
have to be linked explicitly, same as the driver row.

Customer login is normally OTP/phone-based (`POST /auth/otp/request` +
`/otp/verify`), not password -- but `POST /auth/login` doesn't restrict by
role (just email/password), so this script sets a password on the
identity_user for straightforward scripted verification, the same
convenience `seed_e2e_driver.py` already takes for the `driver` role.

Same pattern as `seed_e2e_driver.py` -- raw SQL via the migration/admin
DSN, bypassing RLS, idempotent, safe to re-run.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

EMAIL = "e2e.customer@example.com"
PASSWORD = "correct-horse-battery"  # noqa: S105 - dev-seed-only, not a real secret
FULL_NAME = "E2E Customer"
PHONE_NUMBER = "+919999900098"
# `Customer`'s own domain invariant (`domain/customer/customer.py`) requires
# a consumer_number for any status other than onboarding/pending_approval —
# without one, hydrating this row from the DB raises INVARIANT_VIOLATION on
# every read, not just a write, so it has to be set at insert time.
CONSUMER_NUMBER = "CN-E2E-098"
# Must be a branch that already has priced cylinder types / demo data —
# Hyderabad Central is what every other E2E fixture in this repo uses.
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
            await conn.execute(text("SELECT id FROM identity.role WHERE code = 'customer'"))
        ).scalar()
        if role_id is None:
            print("Error: role 'customer' not found. Make sure migrations are run.")
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
                        "(id, tenant_id, email, phone_number, password_hash, role) "
                        "VALUES (gen_random_uuid(), :tenant_id, :email, :phone, :password_hash, "
                        "'customer') RETURNING id"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "email": EMAIL,
                        "phone": PHONE_NUMBER,
                        "password_hash": pw_hash,
                    },
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

        # See `seed_e2e_driver.py`'s identical comment — raw-SQL insertion
        # bypasses `SqlAlchemyIdentityUserRepository.add()`'s permission
        # materialization, so backfill `identity_user_permission` here too,
        # idempotently (also repairs a previously-empty permission set).
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
                "WHERE r.code = 'customer'"
            ),
            {"user_id": user_id},
        )

        customer_id = (
            await conn.execute(
                text("SELECT id FROM customer.customer WHERE tenant_id = :tenant_id AND phone_number = :phone"),
                {"tenant_id": tenant_id, "phone": PHONE_NUMBER},
            )
        ).scalar()
        if customer_id is None:
            print("Creating customer profile linked to the identity_user above...")
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, full_name, phone_number, customer_type, "
                    "kyc_status, status, consumer_number, identity_user_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :full_name, :phone, "
                    "'domestic', 'verified', 'active', :consumer_number, :identity_user_id)"
                ),
                {
                    "tenant_id": tenant_id,
                    "branch_id": branch_id,
                    "full_name": FULL_NAME,
                    "phone": PHONE_NUMBER,
                    "consumer_number": CONSUMER_NUMBER,
                    "identity_user_id": user_id,
                },
            )
        else:
            # Existing customer profile (e.g. re-run after a partial
            # failure) — make sure the link and consumer_number are there.
            await conn.execute(
                text(
                    "UPDATE customer.customer "
                    "SET identity_user_id = :user_id, "
                    "consumer_number = COALESCE(consumer_number, :consumer_number) "
                    "WHERE id = :customer_id"
                ),
                {"user_id": user_id, "consumer_number": CONSUMER_NUMBER, "customer_id": customer_id},
            )
            print("customer profile already existed — ensured identity_user_id link + consumer_number.")

    await engine.dispose()
    print("\nDone.")
    print(f"Login Email:    {EMAIL}")
    print(f"Login Password: {PASSWORD}")
    print(f"Phone (OTP):    {PHONE_NUMBER}")
    print(f"Branch:         {BRANCH_NAME}")


if __name__ == "__main__":
    asyncio.run(main())
