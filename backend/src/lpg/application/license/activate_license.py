"""Tenant-side license activation — `agency_admin`, `license:manage_tenant`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import LicenseActivationFailedError, LicenseNotActivatedError
from lpg.domain.common.base import InvariantViolation

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.identity.ports import TokenHasher
    from lpg.application.license.ports import LicenseRepository, LicenseStatusChecker
    from lpg.domain.license.license import License


@dataclass(frozen=True, slots=True)
class ActivateLicenseCommand(Command):
    tenant_id: uuid.UUID
    presented_key: str


class ActivateLicenseUseCase:
    def __init__(
        self,
        repository: LicenseRepository,
        token_hasher: TokenHasher,
        status_checker: LicenseStatusChecker,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_hasher = token_hasher
        self._status_checker = status_checker
        self._unit_of_work = unit_of_work

    async def execute(self, command: ActivateLicenseCommand) -> License:
        license_ = await self._repository.get_by_tenant_id(command.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{command.tenant_id}'."
            raise LicenseNotActivatedError(msg, tenant_id=str(command.tenant_id))

        if not self._token_hasher.verify(command.presented_key, license_.key_hash):
            msg = "The presented license key does not match."
            raise LicenseActivationFailedError(msg, tenant_id=str(command.tenant_id))

        try:
            license_.activate(at=datetime.now(UTC))
        except InvariantViolation as exc:  # already activated / revoked
            msg = "This license cannot be activated."
            raise LicenseActivationFailedError(
                msg, tenant_id=str(command.tenant_id)
            ) from exc

        await self._repository.save(license_)
        await self._unit_of_work.commit()
        await self._status_checker.invalidate(command.tenant_id)
        return license_
