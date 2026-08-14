import os
import re

def main():
    files_to_fix = [
        "tests/integration/test_driver_endpoints_smoke.py",
        "tests/integration/test_order_endpoints_smoke.py",
        "tests/integration/test_route_endpoints_smoke.py",
        "tests/integration/test_route_rbac.py",
        "tests/integration/test_driver_rbac.py",
    ]

    seed_employee_code = """
async def _seed_employee(engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee (id, tenant_id, branch_id, employee_code, first_name, last_name, phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, 'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id), "employee_code": f"DRV-{uuid.uuid4().hex[:6]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(employee_id))
"""

    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "def _seed_employee" not in content:
            # Find a place to insert it, maybe after _seed_branch or _seed_staff_user
            if "async def _seed_staff_user" in content:
                content = content.replace("async def _seed_staff_user", seed_employee_code + "\n\nasync def _seed_staff_user")

        # Now fix _seed_driver
        if "def _seed_driver" in content:
            # We need to change _seed_driver to call _seed_employee or insert employee directly
            # Actually, _seed_driver has engine, tenant_id, branch_id. We can just run the insert inside _seed_driver!
            seed_driver_replacement = """        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee (id, tenant_id, branch_id, employee_code, first_name, last_name, phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, 'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id), "employee_code": f"DRV-{uuid.uuid4().hex[:6]}"},
            )
        ).scalar_one()
        identity_user_id"""
            content = content.replace("        identity_user_id", seed_driver_replacement)

            # And replace '"employee_id": str(uuid.uuid4()),' with '"employee_id": str(employee_id),'
            content = content.replace('"employee_id": str(uuid.uuid4()),', '"employee_id": str(employee_id),')

        # Fix test_driver_endpoints_smoke.py and test_driver_rbac.py
        if file_path == "tests/integration/test_driver_endpoints_smoke.py":
            content = content.replace(
                '"employee_id": str(uuid.uuid4()),',
                '# Replaced via script\n'
            )
            content = content.replace(
                'branch_id = await _seed_branch(',
                'employee_id = await _seed_employee(admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id)\n        branch_id = await _seed_branch('
            )
            # Need to inject employee_id into json dict correctly since we replaced it with a comment
            content = content.replace(
                '# Replaced via script',
                '"employee_id": str(employee_id),'
            )

        if file_path == "tests/integration/test_driver_rbac.py":
            # Let's just fix anywhere `str(uuid.uuid4())` is used as employee_id for POST /drivers
            if '"employee_id": str(uuid.uuid4()),' in content:
                content = content.replace(
                    '"employee_id": str(uuid.uuid4()),',
                    '"employee_id": str(employee_id),'
                )
                content = content.replace(
                    'branch_id = await _seed_branch(',
                    'employee_id = await _seed_employee(admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id)\n        branch_id = await _seed_branch('
                )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    main()
