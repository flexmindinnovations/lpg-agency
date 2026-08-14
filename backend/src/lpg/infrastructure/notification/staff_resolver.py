"""Staff resolver implementation."""

import uuid

from lpg.application.identity.ports import IdentityUserRepository
from lpg.application.notification.ports import BranchStaffResolver
from lpg.application.tenant_admin.ports import EmployeeRepository


class EmployeeBranchStaffResolver(BranchStaffResolver):
    """Implements BranchStaffResolver using EmployeeRepository + IdentityUserRepository."""

    def __init__(
        self,
        employee_repo: EmployeeRepository,
        identity_repo: IdentityUserRepository,
    ) -> None:
        self._employee_repo = employee_repo
        self._identity_repo = identity_repo

    async def resolve_for_branch(
        self,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        eligible_roles: frozenset[str],
    ) -> list[uuid.UUID]:
        employees = await self._employee_repo.list_employees(
            branch_id=branch_id, limit=200
        )
        
        user_ids: list[uuid.UUID] = []
        for emp in employees:
            if emp.role not in eligible_roles or emp.status != "active":
                continue
            
            # Resolve to IdentityUser using the phone number
            identity = await self._identity_repo.get_by_phone_number(
                tenant_id, emp.phone_number
            )
            if identity:
                user_ids.append(identity.id)
                
        return user_ids
