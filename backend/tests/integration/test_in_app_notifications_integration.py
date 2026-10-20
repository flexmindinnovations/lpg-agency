"""In-app notifications are written straight after the triggering commit
(DO-27 / CA-05) — against a real Postgres with RLS, no worker involved.

Checks who receives each kind of alert: staff by permission (RBAC), staff
pinned to another branch left out, the person who caused the event left
out, the customer for their own order, and nothing ever crossing into
another tenant. Also checks the text names the order number and customer.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings
    from lpg.infrastructure.persistence.database import Database

pytestmark = pytest.mark.integration


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    from lpg.infrastructure.persistence.database import Database

    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _insert(engine: AsyncEngine, sql: str, **params: Any) -> uuid.UUID:
    async with engine.begin() as conn:
        value = (await conn.execute(text(sql), params)).scalar_one()
    return uuid.UUID(str(value))


async def _tenant(engine: AsyncEngine) -> uuid.UUID:
    return await _insert(
        engine,
        "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
        "VALUES (gen_random_uuid(), 'Notify Tenant', :slug, 'ops@example.com') RETURNING id",
        slug=f"notify-{uuid.uuid4().hex[:10]}",
    )


async def _branch(engine: AsyncEngine, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    return await _insert(
        engine,
        "INSERT INTO tenant.branch (id, tenant_id, name) "
        "VALUES (gen_random_uuid(), :t, :name) RETURNING id",
        t=str(tenant_id),
        name=name,
    )


async def _user(
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    role: str,
    branch_id: uuid.UUID | None = None,
    *,
    active: bool = True,
) -> uuid.UUID:
    """An identity user with its role's permissions materialised, the way
    `insert_identity_user` does it."""
    user_id = await _insert(
        engine,
        "INSERT INTO identity.identity_user (id, tenant_id, branch_id, email, role, is_active) "
        "VALUES (gen_random_uuid(), :t, :b, :email, :role, :active) RETURNING id",
        t=str(tenant_id),
        b=str(branch_id) if branch_id else None,
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=active,
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission (id, user_id, permission_id) "
                "SELECT gen_random_uuid(), :u, rp.permission_id FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id WHERE r.code = :role"
            ),
            {"u": str(user_id), "role": role},
        )
    return user_id


async def _customer_order(
    engine: AsyncEngine, tenant_id: uuid.UUID, branch_id: uuid.UUID, login: uuid.UUID
) -> tuple[uuid.UUID, str]:
    customer_id = await _insert(
        engine,
        "INSERT INTO customer.customer (id, tenant_id, branch_id, full_name, phone_number, "
        "identity_user_id) VALUES (gen_random_uuid(), :t, :b, 'Meena Iyer', :phone, :u) "
        "RETURNING id",
        t=str(tenant_id),
        b=str(branch_id),
        phone=f"+9198{uuid.uuid4().int % 10**8:08d}",
        u=str(login),
    )
    address_id = await _insert(
        engine,
        "INSERT INTO customer.customer_address (id, tenant_id, customer_id, line_1, city, "
        "state, pincode) VALUES (gen_random_uuid(), :t, :c, '12 MG Road', 'Hyderabad', "
        "'Telangana', '500001') RETURNING id",
        t=str(tenant_id),
        c=str(customer_id),
    )
    order_number = f"ORD{uuid.uuid4().int % 10**6:06d}"
    order_id = await _insert(
        engine,
        'INSERT INTO orders."order" (id, tenant_id, branch_id, customer_id, address_id, '
        "delivery_address_line, booking_source, requested_date, status, order_number) "
        "VALUES (gen_random_uuid(), :t, :b, :c, :a, '12 MG Road', 'mobile_app', now(), "
        "'booked', :n) RETURNING id",
        t=str(tenant_id),
        b=str(branch_id),
        c=str(customer_id),
        a=str(address_id),
        n=order_number,
    )
    cylinder_type_id = await _insert(
        engine,
        "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
        "VALUES (gen_random_uuid(), :t, 'Domestic 14.2kg', 14.2) RETURNING id",
        t=str(tenant_id),
    )
    await _insert(
        engine,
        "INSERT INTO orders.order_line (id, order_id, cylinder_type_id, quantity_ordered) "
        "VALUES (gen_random_uuid(), :o, :c, 1) RETURNING id",
        o=str(order_id),
        c=str(cylinder_type_id),
    )
    return order_id, order_number


async def _rows(engine: AsyncEngine, notification_type: str, tenant_id: uuid.UUID) -> list[Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT recipient_user_id, tenant_id, title, body, reference_type, reference_id "
                "FROM notification.in_app_notification "
                "WHERE notification_type = :type AND tenant_id = :t"
            ),
            {"type": notification_type, "t": str(tenant_id)},
        )
        return list(result)


class TestInAppNotificationRecipients:
    async def test_staff_customer_branch_scope_rbac_and_tenant_isolation(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        from lpg.infrastructure.notification.delivery import create_in_app_notifications

        tenant = await _tenant(admin_engine)
        main = await _branch(admin_engine, tenant, "Main")
        other_branch = await _branch(admin_engine, tenant, "West")
        admin = await _user(admin_engine, tenant, "agency_admin")
        manager_main = await _user(admin_engine, tenant, "manager", main)
        manager_west = await _user(admin_engine, tenant, "manager", other_branch)
        dispatcher_main = await _user(admin_engine, tenant, "dispatcher", main)
        accountant = await _user(admin_engine, tenant, "accountant")
        inactive_manager = await _user(admin_engine, tenant, "manager", main, active=False)
        await _user(admin_engine, tenant, "driver", main)
        customer_login = await _user(admin_engine, tenant, "customer", main)
        order_id, order_number = await _customer_order(admin_engine, tenant, main, customer_login)

        other_tenant = await _tenant(admin_engine)
        other_admin = await _user(admin_engine, other_tenant, "agency_admin")

        def payload(notification_type: str, **extra: str) -> dict[str, str]:
            return {
                "type": notification_type,
                "tenant_id": str(tenant),
                "order_id": str(order_id),
                **extra,
            }

        # New order: everyone who can confirm orders for that branch.
        await create_in_app_notifications(database, None, payload("order_placed_staff"))
        rows = await _rows(admin_engine, "order_placed_staff", tenant)
        assert {r.recipient_user_id for r in rows} == {admin, manager_main, dispatcher_main}
        assert manager_west not in {r.recipient_user_id for r in rows}
        assert inactive_manager not in {r.recipient_user_id for r in rows}
        assert accountant not in {r.recipient_user_id for r in rows}
        assert all(r.tenant_id == tenant for r in rows)
        assert rows[0].body == (
            f"{order_number} for Meena Iyer was just placed and is waiting for confirmation."
        )
        assert rows[0].reference_type == "order"
        assert rows[0].reference_id == order_id

        # Cancellation request: approvers only, minus whoever asked.
        await create_in_app_notifications(
            database,
            None,
            payload(
                "cancellation_requested_staff",
                reason="Booked twice",
                actor_id=str(manager_main),
            ),
        )
        rows = await _rows(admin_engine, "cancellation_requested_staff", tenant)
        assert {r.recipient_user_id for r in rows} == {admin}
        assert "Reason: Booked twice." in rows[0].body

        # Customer-facing: the order's own customer, nobody else.
        await create_in_app_notifications(
            database, None, payload("delivery_failed_customer", reason_code="customer_unavailable")
        )
        rows = await _rows(admin_engine, "delivery_failed_customer", tenant)
        assert [r.recipient_user_id for r in rows] == [customer_login]
        assert order_number in rows[0].body
        assert "customer not available" in rows[0].body

        # A complaint can't be "assigned" into another tenant.
        await create_in_app_notifications(
            database,
            None,
            {
                "type": "complaint_assigned",
                "tenant_id": str(tenant),
                "assigned_to": str(other_admin),
            },
        )
        assert await _rows(admin_engine, "complaint_assigned", tenant) == []

        # Nothing was ever written for the other tenant.
        async with admin_engine.connect() as conn:
            leaked = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM notification.in_app_notification "
                        "WHERE tenant_id = :t OR recipient_user_id = :u"
                    ),
                    {"t": str(other_tenant), "u": str(other_admin)},
                )
            ).scalar_one()
        assert leaked == 0

    async def test_an_order_of_another_tenant_resolves_to_nobody(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """RLS: a payload naming tenant A but an order of tenant B finds no
        order, so no one in A is told about B's order."""
        from lpg.infrastructure.notification.delivery import create_in_app_notifications

        tenant_a = await _tenant(admin_engine)
        await _user(admin_engine, tenant_a, "agency_admin")
        tenant_b = await _tenant(admin_engine)
        branch_b = await _branch(admin_engine, tenant_b, "Main")
        login_b = await _user(admin_engine, tenant_b, "customer", branch_b)
        order_b, _ = await _customer_order(admin_engine, tenant_b, branch_b, login_b)

        prepared = await create_in_app_notifications(
            database,
            None,
            {"type": "order_placed_staff", "tenant_id": str(tenant_a), "order_id": str(order_b)},
        )
        assert prepared is None
        assert await _rows(admin_engine, "order_placed_staff", tenant_a) == []
