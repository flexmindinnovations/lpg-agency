"""Notification jobs."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from lpg.domain.notification.in_app_notification import InAppNotification
from lpg.domain.notification.notification_log import NotificationLog

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = structlog.get_logger(__name__)

_STAFF_ALERT_ROLES = frozenset({"agency_admin", "branch_manager", "dispatcher"})

# Notification types whose recipients are "the branch staff for this order's
# branch" rather than the customer or the assigned driver.
_STAFF_BRANCH_TYPES = frozenset({"delivery_failed_staff", "order_placed_staff"})


async def send_notification(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """ARQ job to process and send a notification.

    Payload format:
    {
        "type": "booking_confirmed" | "driver_assigned" | "out_for_delivery" |
                "delivery_confirmed" | "invoice_generated" | "delivery_failed_staff",
        "tenant_id": str,
        "order_id": str,
        # Every type resolves its recipient (customer, the assigned driver
        # for "driver_assigned", or branch staff for "delivery_failed_staff")
        # by fetching the order itself — the payload carries nothing else.
    }
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()),
        job_name="send_notification",
        tenant_id=payload.get("tenant_id"),
    )

    tenant_id = uuid.UUID(payload["tenant_id"])
    notification_type = payload["type"]

    # Imports inside the job to avoid circular dependencies
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database: Database = ctx["database"]

    async for session in database.open_session(tenant_id=tenant_id):
        tenant_context = RequestTenantContext(tenant_id=tenant_id)
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            from lpg.config.settings import get_settings
            from lpg.infrastructure.channels.email_channel import StubEmailChannel
            from lpg.infrastructure.channels.sms_channel import StubSmsChannel
            from lpg.infrastructure.notification.staff_resolver import (
                EmployeeBranchStaffResolver,
            )
            from lpg.infrastructure.persistence.repositories.customer import (
                SqlAlchemyCustomerRepository,
            )
            from lpg.infrastructure.persistence.repositories.driver import (
                SqlAlchemyDriverRepository,
            )
            from lpg.infrastructure.persistence.repositories.employee import (
                SqlAlchemyEmployeeRepository,
            )
            from lpg.infrastructure.persistence.repositories.identity import (
                SqlAlchemyIdentityUserRepository,
            )
            from lpg.infrastructure.persistence.repositories.notification import (
                SqlAlchemyDeviceTokenRepository,
                SqlAlchemyInAppNotificationRepository,
                SqlAlchemyNotificationLogRepository,
            )
            from lpg.infrastructure.persistence.repositories.order import (
                SqlAlchemyOrderRepository,
            )
            from lpg.infrastructure.persistence.repositories.route import (
                SqlAlchemyRouteRepository,
            )
            from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

            field_encryptor = FernetFieldEncryptor(get_settings())

            in_app_repo = SqlAlchemyInAppNotificationRepository(session)
            log_repo = SqlAlchemyNotificationLogRepository(uow)
            device_repo = SqlAlchemyDeviceTokenRepository(session)
            identity_repo = SqlAlchemyIdentityUserRepository(database)

            # Resolve recipients. None of the order-lifecycle handlers
            # (`notification_handlers.py`) put anything but `order_id` on the
            # payload, so every type below resolves its recipient by fetching
            # the order itself rather than trusting extra payload fields.
            recipient_user_ids: list[uuid.UUID] = []

            order_repo = SqlAlchemyOrderRepository(uow)
            order = await order_repo.get_by_id(uuid.UUID(payload["order_id"]))
            if order is None:
                _logger.warning("order_not_found", order_id=payload["order_id"])
            elif notification_type in _STAFF_BRANCH_TYPES:
                employee_repo = SqlAlchemyEmployeeRepository(uow)
                resolver = EmployeeBranchStaffResolver(employee_repo, identity_repo)
                recipient_user_ids = await resolver.resolve_for_branch(
                    tenant_id=tenant_id,
                    branch_id=order.branch_id,
                    eligible_roles=_STAFF_ALERT_ROLES,
                )
            elif notification_type == "driver_assigned":
                # This one goes to the driver who was just assigned, not the
                # customer — resolved via the order's `route_stop_id` -> its
                # `Route`'s `driver_id`, the same path `order.py`'s
                # `_require_own_driver_order` ownership check uses.
                if order.route_stop_id is not None:
                    route_repo = SqlAlchemyRouteRepository(uow)
                    owner = await route_repo.get_stop_owner(order.route_stop_id)
                    if owner is not None:
                        driver_repo = SqlAlchemyDriverRepository(uow)
                        driver = await driver_repo.get_by_id(owner.driver_id)
                        if driver and driver.identity_user_id:
                            recipient_user_ids = [driver.identity_user_id]
            else:
                customer_repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = await customer_repo.get_by_id(order.customer_id)
                if customer and customer.identity_user_id:
                    recipient_user_ids = [customer.identity_user_id]

            if not recipient_user_ids:
                _logger.warning("no_recipients_found", notification_type=notification_type)
                return

            # Format content
            title = _get_title(notification_type)
            body = _get_body(notification_type, payload)
            reference_type = "order"
            reference_id = uuid.UUID(payload["order_id"]) if "order_id" in payload else None

            email_channel = StubEmailChannel()
            sms_channel = StubSmsChannel()
            # Built once at worker startup (holds an OAuth token + httpx
            # client); `StubPushChannel` when Firebase isn't configured.
            from lpg.infrastructure.channels.push_channel import build_push_channel

            push_channel = ctx.get("push_channel") or build_push_channel(get_settings())

            push_data = {
                "type": notification_type,
                **(
                    {"reference_type": reference_type, "reference_id": str(reference_id)}
                    if reference_id is not None
                    else {}
                ),
            }

            for user_id in recipient_user_ids:
                # 1. In-App Notification (Always)
                in_app = InAppNotification.create(
                    tenant_id=tenant_id,
                    recipient_user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    reference_type=reference_type,
                    reference_id=reference_id,
                )
                await in_app_repo.add(in_app)

                # Retrieve IdentityUser for external channels
                user = await identity_repo.get(user_id)
                if not user:
                    continue

                # 2. Email Channel
                if _should_send_email(notification_type) and user.email:
                    email_log = NotificationLog.create(
                        tenant_id=tenant_id,
                        recipient_user_id=user_id,
                        notification_type=notification_type,
                        channel="email",
                        recipient_address=user.email,
                        subject=title,
                        body=body,
                        reference_type=reference_type,
                        reference_id=reference_id,
                    )
                    await log_repo.add(email_log)

                    try:
                        await email_channel.send(to=user.email, subject=title, body=body)
                        email_log.mark_sent()
                    except Exception as e:
                        email_log.mark_failed(str(e))
                        _logger.exception("email_send_failed", user_id=str(user_id))

                    await log_repo.save(email_log)

                # 3. SMS Channel
                if _should_send_sms(notification_type) and user.phone_number:
                    sms_log = NotificationLog.create(
                        tenant_id=tenant_id,
                        recipient_user_id=user_id,
                        notification_type=notification_type,
                        channel="sms",
                        recipient_address=user.phone_number,
                        subject=None,
                        body=body,
                        reference_type=reference_type,
                        reference_id=reference_id,
                    )
                    await log_repo.add(sms_log)

                    try:
                        await sms_channel.send(to=user.phone_number, body=body)
                        sms_log.mark_sent()
                    except Exception as e:
                        sms_log.mark_failed(str(e))
                        _logger.exception("sms_send_failed", user_id=str(user_id))

                    await log_repo.save(sms_log)

                # 4. Push Channel — one FCM request per registered device.
                if _should_send_push(notification_type):
                    from lpg.application.notification.ports import PushTokenInvalidError

                    for device in await device_repo.list_for_user(user_id):
                        push_log = NotificationLog.create(
                            tenant_id=tenant_id,
                            recipient_user_id=user_id,
                            notification_type=notification_type,
                            channel="push",
                            recipient_address=f"{device.platform}:...{device.token[-8:]}",
                            subject=title,
                            body=body,
                            reference_type=reference_type,
                            reference_id=reference_id,
                        )
                        await log_repo.add(push_log)

                        try:
                            await push_channel.send(
                                token=device.token,
                                platform=device.platform,
                                title=title,
                                body=body,
                                data=push_data,
                            )
                            push_log.mark_sent()
                        except PushTokenInvalidError:
                            # Dead token — prune it so we stop trying.
                            await device_repo.delete_by_token(device.token)
                            push_log.mark_failed("token unregistered")
                            _logger.info(
                                "push_token_pruned", token_suffix=device.token[-8:]
                            )
                        except Exception as e:
                            push_log.mark_failed(str(e))
                            _logger.exception("push_send_failed", user_id=str(user_id))

                        await log_repo.save(push_log)

            _logger.info("notification_job_completed", recipients_count=len(recipient_user_ids))


def _get_title(notification_type: str) -> str:
    titles = {
        "booking_confirmed": "Order Confirmed",
        "driver_assigned": "New Delivery Assigned",
        "out_for_delivery": "Out for Delivery",
        "delivery_confirmed": "Delivery Confirmed",
        "invoice_generated": "Invoice Generated",
        "delivery_failed_staff": "Delivery Failed Alert",
        "order_placed_staff": "New Order",
    }
    return titles.get(notification_type, "Notification")


def _get_body(notification_type: str, payload: dict[str, Any]) -> str:
    order_id_short = payload.get("order_id", "Unknown")[:8].upper()
    bodies = {
        "booking_confirmed": f"Your order #{order_id_short} has been confirmed.",
        "driver_assigned": f"You've been assigned to deliver order #{order_id_short}.",
        "out_for_delivery": f"Your order #{order_id_short} is out for delivery.",
        "delivery_confirmed": f"Your order #{order_id_short} has been delivered successfully.",
        "invoice_generated": f"An invoice has been generated for your order #{order_id_short}.",
        "delivery_failed_staff": (
            f"Delivery failed for order #{order_id_short}. Please check the system."
        ),
        "order_placed_staff": (
            f"Order #{order_id_short} was just placed and is awaiting confirmation."
        ),
    }
    return bodies.get(notification_type, "You have a new notification.")


def _should_send_email(notification_type: str) -> bool:
    return notification_type in {"booking_confirmed", "delivery_confirmed", "invoice_generated"}


def _should_send_sms(notification_type: str) -> bool:
    return notification_type in {
        "booking_confirmed",
        "driver_assigned",
        "out_for_delivery",
        "delivery_confirmed",
    }


def _should_send_push(notification_type: str) -> bool:
    # Every customer- and driver-facing lifecycle event. `delivery_failed_
    # staff` is intentionally excluded — staff use the dashboard, not the
    # mobile apps that register device tokens.
    return notification_type in {
        "booking_confirmed",
        "driver_assigned",
        "out_for_delivery",
        "delivery_confirmed",
        "invoice_generated",
    }
