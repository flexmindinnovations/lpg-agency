"""Infrastructure behind device control (ADR-071).

- `RedisDeviceControlModeReader`: the agency's `device_control` mode, cached
  about a minute.
- `RedisDeviceAccessReader`: one phone's status and identifier hash, cached
  about thirty seconds and cleared the moment an admin changes the phone.
- `SqlAlchemyDeviceRegistrar`: records a phone at sign-in, in its own
  tenant-scoped transaction (sign-in has no tenant session yet).

Both readers treat a cache outage as a miss and fall back to the database —
Redis is a performance layer here, never a correctness dependency. Reads go
through a tenant-scoped session, so row-level security applies to them like
to any other query.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.license.device_access import DeviceAccess
from lpg.application.license.manage_devices import (
    DeviceRegistration,
    NameOwnDeviceCommand,
    NameOwnDeviceUseCase,
    RegisterDeviceCommand,
    RegisterDeviceUseCase,
)
from lpg.config.logging import get_logger
from lpg.domain.license.device_control import DEVICE_CONTROL_CONFIG_KEY, DeviceControlMode
from lpg.domain.license.linked_device import DeviceStatus
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver
from lpg.infrastructure.persistence.audit_trail import SqlAlchemyAuditTrail
from lpg.infrastructure.persistence.models.platform import LinkedDeviceModel
from lpg.infrastructure.persistence.repositories.license import (
    SqlAlchemyLicenseRepository,
    SqlAlchemyLinkedDeviceRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import CacheClient
    from lpg.domain.license.linked_device import LinkedDevice
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

_MODE_TTL_SECONDS = 60
_ACCESS_TTL_SECONDS = 30


def _mode_key(tenant_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:device_control:mode"


def _access_key(tenant_id: uuid.UUID, device_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:device:{device_id}:access"


class RedisDeviceControlModeReader:
    def __init__(self, cache: CacheClient, database: Database) -> None:
        self._cache = cache
        self._database = database

    async def get(self, tenant_id: uuid.UUID) -> DeviceControlMode:
        key = _mode_key(tenant_id)
        try:
            cached = await self._cache.get(key)
        except Exception as exc:  # noqa: BLE001 - a cache outage degrades to a DB read
            _logger.warning("device_mode_cache_read_failed", error=str(exc))
            cached = None
        if cached is not None:
            return DeviceControlMode.parse(cached)

        mode = await self._read(tenant_id)
        try:
            await self._cache.set(key, mode.value, ttl_seconds=_MODE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001 - caching is best-effort
            _logger.warning("device_mode_cache_write_failed", error=str(exc))
        return mode

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        try:
            await self._cache.delete(_mode_key(tenant_id))
        except Exception as exc:  # noqa: BLE001 - the TTL expires it either way
            _logger.warning("device_mode_cache_invalidate_failed", error=str(exc))

    async def _read(self, tenant_id: uuid.UUID) -> DeviceControlMode:
        async for session in self._database.open_session(tenant_id=tenant_id):
            context = RequestTenantContext(tenant_id=tenant_id)
            uow = SqlAlchemyUnitOfWork(session, context)
            entries = await SqlAlchemyTenantConfigurationRepository(uow).list_for_tenant_and_key(
                tenant_id, DEVICE_CONTROL_CONFIG_KEY
            )
            effective = TenantConfigurationResolver.resolve(
                entries, DEVICE_CONTROL_CONFIG_KEY, datetime.now(UTC)
            )
            return DeviceControlMode.parse(effective.config_value if effective else None)
        return DeviceControlMode.OFF  # pragma: no cover - open_session yields once


class RedisDeviceAccessReader:
    def __init__(self, cache: CacheClient, database: Database) -> None:
        self._cache = cache
        self._database = database

    async def get(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> DeviceAccess | None:
        key = _access_key(tenant_id, device_id)
        try:
            cached = await self._cache.get(key)
        except Exception as exc:  # noqa: BLE001 - a cache outage degrades to a DB read
            _logger.warning("device_access_cache_read_failed", error=str(exc))
            cached = None
        if cached is not None:
            return _decode(cached)

        access = await self._read(tenant_id, device_id)
        try:
            await self._cache.set(key, _encode(access), ttl_seconds=_ACCESS_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001 - caching is best-effort
            _logger.warning("device_access_cache_write_failed", error=str(exc))
        return access

    async def invalidate(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> None:
        try:
            await self._cache.delete(_access_key(tenant_id, device_id))
        except Exception as exc:  # noqa: BLE001 - the TTL expires it either way
            _logger.warning("device_access_cache_invalidate_failed", error=str(exc))

    async def _read(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> DeviceAccess | None:
        async for session in self._database.open_session(tenant_id=tenant_id):
            row = (
                await session.execute(
                    select(LinkedDeviceModel).where(
                        LinkedDeviceModel.id == device_id,
                        LinkedDeviceModel.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return DeviceAccess(
                device_id=row.id,
                app_type=row.app_type,
                status=DeviceStatus(row.status),
                identifier_hash=row.device_identifier,
                display_name=row.display_name,
                name_confirmed=row.name_confirmed,
            )
        return None  # pragma: no cover - open_session yields once


def _encode(access: DeviceAccess | None) -> str:
    # A missing device is cached too ("null"), so a deleted device's tokens do
    # not hit the database on every request.
    if access is None:
        return "null"
    return json.dumps(
        {
            "device_id": str(access.device_id),
            "app_type": access.app_type,
            "status": access.status.value,
            "identifier_hash": access.identifier_hash,
            "display_name": access.display_name,
            "name_confirmed": access.name_confirmed,
        }
    )


def _decode(raw: str) -> DeviceAccess | None:
    import uuid as _uuid

    data = json.loads(raw)
    if data is None:
        return None
    return DeviceAccess(
        device_id=_uuid.UUID(data["device_id"]),
        app_type=data["app_type"],
        status=DeviceStatus(data["status"]),
        identifier_hash=data["identifier_hash"],
        display_name=data["display_name"],
        name_confirmed=data.get("name_confirmed", True),
    )


class SqlAlchemyDeviceRegistrar:
    def __init__(self, database: Database, event_dispatcher: DomainEventDispatcher | None) -> None:
        self._database = database
        self._event_dispatcher = event_dispatcher

    async def register(self, command: RegisterDeviceCommand) -> DeviceRegistration:
        try:
            return await self._register_once(command)
        except IntegrityError:
            # Two sign-ins from a brand-new phone raced to create the same
            # record; the loser finds the winner's row on the second pass.
            return await self._register_once(command)

    async def _register_once(self, command: RegisterDeviceCommand) -> DeviceRegistration:
        context = RequestTenantContext(
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            user_display_name=command.user_name,
        )
        async for session in self._database.open_session(tenant_id=command.tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, context, event_dispatcher=self._event_dispatcher
            ) as uow:
                use_case = RegisterDeviceUseCase(
                    SqlAlchemyLicenseRepository(uow),
                    SqlAlchemyLinkedDeviceRepository(uow),
                    SqlAlchemyAuditTrail(uow),
                    uow,
                )
                return await use_case.execute(command)
        msg = "open_session yielded no session"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover


class SqlAlchemyDeviceNamer:
    """Runs `NameOwnDeviceUseCase` in its own tenant-scoped transaction, so a
    phone that is still waiting for approval can name itself."""

    def __init__(self, database: Database, event_dispatcher: DomainEventDispatcher | None) -> None:
        self._database = database
        self._event_dispatcher = event_dispatcher

    async def name(self, command: NameOwnDeviceCommand) -> LinkedDevice:
        context = RequestTenantContext(tenant_id=command.tenant_id, user_id=command.user_id)
        async for session in self._database.open_session(tenant_id=command.tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, context, event_dispatcher=self._event_dispatcher
            ) as uow:
                use_case = NameOwnDeviceUseCase(
                    SqlAlchemyLinkedDeviceRepository(uow), SqlAlchemyAuditTrail(uow), uow
                )
                return await use_case.execute(command)
        msg = "open_session yielded no session"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover
