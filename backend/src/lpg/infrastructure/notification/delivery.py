"""Delivering a notification: the in-app row, then email / SMS / push.

**In-app rows are written in the API process, synchronously after the
triggering transaction commits** (`InAppFirstNotifier`), and only the
external channels go to the arq worker. The bell, the customer's inbox and
the driver's Alerts tab are the system of record for "something needs your
attention" — a cancellation waiting for approval has no other way to reach
a manager — so they must not depend on a background worker being up. Push,
SMS and email are slow third-party calls with retries, which is exactly
what the worker is for.

Writing the row registers the `InAppNotification` with its unit of work,
so `InAppNotificationCreated` is dispatched after commit and the realtime
handler publishes `notification.new` to the recipient's channel — the
client's badge, toast and inbox update without a refresh.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from lpg.domain.notification.in_app_notification import InAppNotification
from lpg.domain.notification.notification_log import NotificationLog
from lpg.infrastructure.notification.catalog import sms_variables, spec_for
from lpg.infrastructure.notification.recipients import (
    NotificationResolver,
    PreparedNotification,
)

if TYPE_CHECKING:
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

_logger = structlog.get_logger(__name__)

#: Set on a payload whose in-app rows the API process already wrote, so the
#: worker only does the external channels.
IN_APP_DELIVERED = "in_app_delivered"


class Notifier(Protocol):
    """What event handlers hand a notification payload to."""

    async def notify(self, payload: dict[str, Any]) -> None: ...


async def write_in_app(uow: SqlAlchemyUnitOfWork, prepared: PreparedNotification) -> None:
    """One `InAppNotification` per recipient, in `uow`'s transaction."""
    from lpg.infrastructure.persistence.repositories.notification import (
        SqlAlchemyInAppNotificationRepository,
    )

    repo = SqlAlchemyInAppNotificationRepository(uow.session)
    tenant_id = uow.tenant_context.tenant_id
    for user_id in prepared.recipient_user_ids:
        notification = InAppNotification.create(
            tenant_id=tenant_id,
            recipient_user_id=user_id,
            notification_type=prepared.notification_type,
            title=prepared.title,
            body=prepared.body,
            reference_type=prepared.reference_type,
            reference_id=prepared.reference_id,
        )
        await repo.add(notification)
        # `add` is raw SQL and doesn't track the aggregate — register it so
        # `InAppNotificationCreated` reaches the realtime handler on commit.
        uow.register_aggregate(notification)


async def create_in_app_notifications(
    database: Database,
    event_dispatcher: DomainEventDispatcher | None,
    payload: dict[str, Any],
) -> PreparedNotification | None:
    """Resolve and write the in-app rows in their own tenant-scoped
    transaction. Returns what was written (None when nobody qualifies)."""
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    tenant_id = uuid.UUID(str(payload["tenant_id"]))
    prepared: PreparedNotification | None = None
    async for session in database.open_session(tenant_id=tenant_id):
        # No dispatcher on the unit of work: the `InAppNotificationCreated`
        # events are dispatched below, after commit, where a realtime
        # publish failure can be told apart from a failed write.
        async with SqlAlchemyUnitOfWork(session, RequestTenantContext(tenant_id=tenant_id)) as uow:
            prepared = await NotificationResolver(uow, tenant_id).prepare(payload)
            if prepared is None:
                return None
            await write_in_app(uow, prepared)
            await uow.commit()
            events = uow.collect_events()
    if prepared is not None and event_dispatcher is not None:
        try:
            await event_dispatcher.dispatch(events)
        except Exception:
            # Rows are saved; clients pick them up on their next fetch.
            _logger.warning("in_app_notification_publish_failed", exc_info=True)
    return prepared


class InAppFirstNotifier:
    """The API process's `Notifier`: in-app rows now, external channels via
    the worker.

    Never raises — it runs after the user's own transaction committed, and
    a notification problem must not turn their successful action into an
    error response (the dispatcher re-raises handler failures). Failures
    are logged with the payload type for follow-up.
    """

    def __init__(
        self,
        database: Database,
        event_dispatcher: DomainEventDispatcher | None,
        job_queue: JobQueue | None,
    ) -> None:
        self._database = database
        self._event_dispatcher = event_dispatcher
        self._job_queue = job_queue

    async def notify(self, payload: dict[str, Any]) -> None:
        notification_type = payload.get("type")
        try:
            prepared = await create_in_app_notifications(
                self._database, self._event_dispatcher, payload
            )
        except Exception:
            _logger.exception("in_app_notification_failed", notification_type=notification_type)
            prepared = None
            # Let the worker try the whole thing (in-app included) instead.
            await self._enqueue(payload)
            return
        if prepared is None:
            return
        spec = spec_for(str(notification_type))
        if spec is not None and (spec.has_external_channel or prepared.push):
            await self._enqueue({**payload, IN_APP_DELIVERED: True})

    async def _enqueue(self, payload: dict[str, Any]) -> None:
        if self._job_queue is None:
            return
        try:
            await self._job_queue.enqueue("send_notification", payload)
        except Exception:
            _logger.exception("notification_enqueue_failed", notification_type=payload.get("type"))


async def deliver_external(
    ctx: dict[str, Any],
    uow: SqlAlchemyUnitOfWork,
    database: Database,
    prepared: PreparedNotification,
) -> None:
    """Email, SMS and push for each recipient, each attempt logged to
    `notification_log`. Runs in the worker."""
    from lpg.application.notification.ports import PushTokenInvalidError
    from lpg.config.settings import get_settings
    from lpg.infrastructure.channels.email_channel import StubEmailChannel
    from lpg.infrastructure.channels.push_channel import build_push_channel
    from lpg.infrastructure.channels.sms_channel import build_sms_channel
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyIdentityUserRepository,
    )
    from lpg.infrastructure.persistence.repositories.notification import (
        SqlAlchemyDeviceTokenRepository,
        SqlAlchemyNotificationLogRepository,
    )

    spec = prepared.spec
    if not (spec.email or spec.sms is not None or prepared.push):
        return

    tenant_id = uow.tenant_context.tenant_id
    log_repo = SqlAlchemyNotificationLogRepository(uow)
    device_repo = SqlAlchemyDeviceTokenRepository(uow.session)
    identity_repo = SqlAlchemyIdentityUserRepository(database)
    email_channel = StubEmailChannel()
    # Built once at worker startup (they hold httpx clients / OAuth tokens);
    # stubs when no provider is configured.
    sms_channel = ctx.get("sms_channel") or build_sms_channel(get_settings())
    push_channel = ctx.get("push_channel") or build_push_channel(get_settings())

    title, body = prepared.title, prepared.body
    ref_type, ref_id = prepared.reference_type, prepared.reference_id
    push_data = {
        "type": prepared.notification_type,
        **({"reference_type": ref_type, "reference_id": str(ref_id)} if ref_id else {}),
    }

    def _log(user_id: uuid.UUID, channel: str, address: str, subject: str | None) -> Any:
        return NotificationLog.create(
            tenant_id=tenant_id,
            recipient_user_id=user_id,
            notification_type=prepared.notification_type,
            channel=channel,
            recipient_address=address,
            subject=subject,
            body=body,
            reference_type=ref_type,
            reference_id=ref_id,
        )

    for user_id in prepared.recipient_user_ids:
        user = await identity_repo.get(user_id)
        if user is None:
            continue

        if spec.email and user.email:
            log = _log(user_id, "email", user.email, title)
            await log_repo.add(log)
            try:
                await email_channel.send(to=user.email, subject=title, body=body)
                log.mark_sent()
            except Exception as exc:
                log.mark_failed(str(exc))
                _logger.exception("email_send_failed", user_id=str(user_id))
            await log_repo.save(log)

        if spec.sms is not None and user.phone_number:
            log = _log(user_id, "sms", user.phone_number, None)
            await log_repo.add(log)
            try:
                await sms_channel.send(
                    to=user.phone_number,
                    body=body,
                    template=spec.sms,
                    variables=sms_variables(prepared.facts),
                )
                log.mark_sent()
            except Exception as exc:
                log.mark_failed(str(exc))
                _logger.exception("sms_send_failed", user_id=str(user_id))
            await log_repo.save(log)

        if prepared.push:
            for device in await device_repo.list_for_user(user_id):
                log = _log(user_id, "push", f"{device.platform}:...{device.token[-8:]}", title)
                await log_repo.add(log)
                try:
                    await push_channel.send(
                        token=device.token,
                        platform=device.platform,
                        title=title,
                        body=body,
                        data=push_data,
                    )
                    log.mark_sent()
                except PushTokenInvalidError:
                    await device_repo.delete_by_token(device.token)
                    log.mark_failed("token unregistered")
                    _logger.info("push_token_pruned", token_suffix=device.token[-8:])
                except Exception as exc:
                    log.mark_failed(str(exc))
                    _logger.exception("push_send_failed", user_id=str(user_id))
                await log_repo.save(log)
