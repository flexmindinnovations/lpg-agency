"""Reacting to a phone's change of state (ADR-071), after the transaction
that changed it has committed.

An admin decision is already saved when these run, and request checks refuse a
blocked phone from the database truth within seconds either way, so every step
here is best-effort: a failure is logged loudly but never turns an already
committed decision into an error for the admin.

- clear the cached status, so the next request sees the new state at once;
- on block or removal, revoke the phone's refresh tokens, so it cannot renew;
- tell the signed-in app over the realtime channel to re-check (the message
  carries no identifier — the app asks the server for its own state).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.config.logging import get_logger
from lpg.domain.license.linked_device import (
    DeviceDeleted,
    DeviceIdentifierRebound,
    DeviceStatus,
    DeviceStatusChanged,
)
from lpg.infrastructure.license.device_access import RedisDeviceAccessReader
from lpg.infrastructure.persistence.repositories.identity import SqlAlchemyRefreshTokenRepository
from lpg.infrastructure.redis.cache import RedisCacheClient

if TYPE_CHECKING:
    from lpg.application.common.ports import RealtimePublisher
    from lpg.application.identity.ports import RefreshTokenRepository
    from lpg.application.license.ports import DeviceAccessReader
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database
    from lpg.infrastructure.redis.client import RedisClient

_logger = get_logger(__name__)

#: States that end the phone's sessions.
_SESSION_ENDING = frozenset({DeviceStatus.BLOCKED.value, DeviceStatus.REMOVED.value})


def register_device_handlers(
    dispatcher: DomainEventDispatcher,
    database: Database,
    redis: RedisClient,
    publisher: RealtimePublisher,
) -> None:
    access: DeviceAccessReader = RedisDeviceAccessReader(RedisCacheClient(redis), database)
    refresh_tokens: RefreshTokenRepository = SqlAlchemyRefreshTokenRepository(database)

    async def on_status_changed(event: DomainEvent) -> None:
        assert isinstance(event, DeviceStatusChanged)

        await access.invalidate(event.tenant_id, event.device_id)

        if event.new_status in _SESSION_ENDING:
            try:
                await refresh_tokens.revoke_all_for_device(event.device_id)
            except Exception:
                _logger.exception("device_token_revocation_failed", device_id=str(event.device_id))

        if event.user_id is not None:
            try:
                await publisher.publish(
                    f"tenant:{event.tenant_id}:user:{event.user_id}",
                    {"type": "device.status_changed", "status": event.new_status},
                )
            except Exception:
                _logger.exception("device_realtime_publish_failed", device_id=str(event.device_id))

    async def on_identifier_rebound(event: DomainEvent) -> None:
        assert isinstance(event, DeviceIdentifierRebound)
        # The cached record still holds the old install ID's hash.
        await access.invalidate(event.tenant_id, event.device_id)

    async def on_deleted(event: DomainEvent) -> None:
        assert isinstance(event, DeviceDeleted)
        # The record is gone (its refresh tokens went with it): drop the cached
        # copy and tell the signed-in app, which will find itself unknown.
        await access.invalidate(event.tenant_id, event.device_id)
        if event.user_id is not None:
            try:
                await publisher.publish(
                    f"tenant:{event.tenant_id}:user:{event.user_id}",
                    {"type": "device.status_changed", "status": DeviceStatus.REMOVED.value},
                )
            except Exception:
                _logger.exception("device_realtime_publish_failed", device_id=str(event.device_id))

    dispatcher.register(DeviceStatusChanged, on_status_changed)
    dispatcher.register(DeviceIdentifierRebound, on_identifier_rebound)
    dispatcher.register(DeviceDeleted, on_deleted)
