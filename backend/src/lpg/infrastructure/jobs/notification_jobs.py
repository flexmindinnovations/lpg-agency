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

# Roles that receive operational alerts. `manager` is the actual role
# string used everywhere (`order.py` / `route.py`'s own
# `principal.role in ("dispatcher", "manager")` checks, the seed data, the
# `tenant.employee` table) — it was previously `branch_manager`, which no
# code path ever produces, so managers silently never got
# `delivery_failed_staff` alerts.
_STAFF_ALERT_ROLES = frozenset({"agency_admin", "manager", "dispatcher"})

# Never an alert recipient regardless of type.
_NON_STAFF_ROLES = frozenset({"customer", "driver"})


async def send_notification(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """ARQ job to process and send a notification.

    Payload format:
    {
        "type": "order_placed" | "booking_confirmed" | "driver_assigned" |
                "out_for_delivery" | "delivery_confirmed" | "invoice_generated" |
                "delivery_failed_staff" | "order_placed_staff",
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
        async with SqlAlchemyUnitOfWork(
            session, tenant_context, event_dispatcher=ctx.get("event_dispatcher")
        ) as uow:
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

            # Resolve recipients. The order-lifecycle handlers
            # (`notification_handlers.py`) put nothing but `order_id` on the
            # payload and resolve their recipient by fetching the order;
            # `cash_shortfall_staff` is route-scoped and carries no order.
            recipient_user_ids: list[uuid.UUID] = []

            # `route_ready` is a mid-route addition the driver must know about
            # now; `driver_assigned` for a still-being-built route is covered
            # by the one `route_ready` push, so its push/SMS is suppressed.
            driver_assigned_live = False

            order_repo = SqlAlchemyOrderRepository(uow)
            order = (
                await order_repo.get_by_id(uuid.UUID(payload["order_id"]))
                if "order_id" in payload
                else None
            )
            if notification_type == "route_ready":
                driver = await SqlAlchemyDriverRepository(uow).get_by_id(
                    uuid.UUID(payload["driver_id"])
                )
                if driver is not None and driver.identity_user_id is not None:
                    recipient_user_ids = [driver.identity_user_id]
                route = await SqlAlchemyRouteRepository(uow).get_by_id(
                    uuid.UUID(payload["route_id"])
                )
                payload["stop_count"] = str(len(route.stops)) if route is not None else "?"
            elif notification_type == "cash_shortfall_staff":
                # Tenant-wide ops team — a cash discrepancy is the office's
                # problem, not one branch's. Same identity-role resolution as
                # `order_placed_staff` (the demo seed doesn't wire the
                # employee -> phone -> identity hop `EmployeeBranchStaffResolver`
                # needs).
                from lpg.infrastructure.persistence.repositories.identity import (
                    SqlAlchemyStaffUserRepository,
                )

                staff_repo = SqlAlchemyStaffUserRepository(database, tenant_id)
                staff = await staff_repo.list_for_tenant(
                    tenant_id, exclude_roles=_NON_STAFF_ROLES
                )
                recipient_user_ids = [
                    u.id for u in staff if u.role in _STAFF_ALERT_ROLES and u.is_active
                ]
            elif order is None:
                _logger.warning("order_not_found", order_id=payload.get("order_id"))
            elif notification_type == "delivery_failed_staff":
                employee_repo = SqlAlchemyEmployeeRepository(uow)
                resolver = EmployeeBranchStaffResolver(employee_repo, identity_repo)
                recipient_user_ids = await resolver.resolve_for_branch(
                    tenant_id=tenant_id,
                    branch_id=order.branch_id,
                    eligible_roles=_STAFF_ALERT_ROLES,
                )
            elif notification_type == "order_placed_staff":
                # Whole ops team, tenant-wide — resolved straight off the
                # `identity.identity_user` role (not the employee ->
                # phone -> identity hop `EmployeeBranchStaffResolver`
                # does, which the demo seed doesn't wire up). A new order
                # is everyone's business at a small agency; branch scoping
                # can come back if a tenant actually runs branches
                # independently.
                from lpg.infrastructure.persistence.repositories.identity import (
                    SqlAlchemyStaffUserRepository,
                )

                staff_repo = SqlAlchemyStaffUserRepository(database, tenant_id)
                staff = await staff_repo.list_for_tenant(
                    tenant_id, exclude_roles=_NON_STAFF_ROLES
                )
                recipient_user_ids = [
                    u.id
                    for u in staff
                    if u.role in _STAFF_ALERT_ROLES and u.is_active
                ]
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
                        route = await route_repo.get_by_id(owner.route_id)
                        driver_assigned_live = (
                            route is not None and route.status == "in_progress"
                        )
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
            reference_type: str
            reference_id: uuid.UUID | None
            if notification_type == "cash_shortfall_staff":
                reference_type = "cash_handover"
                reference_id = uuid.UUID(payload["cash_handover_id"])
            elif notification_type == "route_ready":
                reference_type = "route"
                reference_id = uuid.UUID(payload["route_id"])
            else:
                reference_type = "order"
                reference_id = (
                    uuid.UUID(payload["order_id"]) if "order_id" in payload else None
                )

            # Channels — per instance, not just per type: a `driver_assigned`
            # only pushes for a live mid-route addition.
            send_email = _should_send_email(notification_type)
            send_sms = _should_send_sms(notification_type)
            send_push = _should_send_push(notification_type)
            if notification_type == "driver_assigned":
                send_push = driver_assigned_live

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
                # `SqlAlchemyInAppNotificationRepository.add` is raw SQL and
                # doesn't track the aggregate — register it so
                # `InAppNotificationCreated` reaches the realtime handler on
                # commit and the client's unread badge updates live.
                uow.register_aggregate(in_app)

                # Retrieve IdentityUser for external channels
                user = await identity_repo.get(user_id)
                if not user:
                    continue

                # 2. Email Channel
                if send_email and user.email:
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
                if send_sms and user.phone_number:
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
                if send_push:
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
        "order_placed": "Order Received",
        "booking_confirmed": "Order Confirmed",
        "driver_assigned": "New Delivery Assigned",
        "out_for_delivery": "Out for Delivery",
        "delivery_confirmed": "Delivery Confirmed",
        "invoice_generated": "Invoice Generated",
        "delivery_failed_staff": "Delivery Failed Alert",
        "order_placed_staff": "New Order",
        "cash_shortfall_staff": "Cash Shortfall Declared",
        "route_ready": "Route Ready",
    }
    return titles.get(notification_type, "Notification")


def _get_body(notification_type: str, payload: dict[str, Any]) -> str:
    order_id_short = payload.get("order_id", "Unknown")[:8].upper()
    if notification_type == "cash_shortfall_staff":
        route_short = payload.get("route_id", "Unknown")[:8].upper()
        return (
            f"Cash shortfall of ₹{payload.get('shortfall', '?')} on route "
            f"#{route_short}: expected ₹{payload.get('expected_amount', '?')}, "
            f"driver handed over ₹{payload.get('actual_amount', '?')}."
        )
    if notification_type == "route_ready":
        stops = payload.get("stop_count", "?")
        plural = "" if stops == "1" else "s"
        return f"Your route is ready — {stops} stop{plural}."
    bodies = {
        "order_placed": (
            f"We've received your order #{order_id_short}. "
            "You'll be notified once the agency confirms it."
        ),
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
    # `cash_shortfall_staff` also goes to email — a money discrepancy wants a
    # written trail the office can forward, not just a dashboard badge.
    return notification_type in {
        "booking_confirmed",
        "delivery_confirmed",
        "invoice_generated",
        "cash_shortfall_staff",
    }


def _should_send_sms(notification_type: str) -> bool:
    # `driver_assigned` dropped SMS with Phase 25-B — the driver app has push
    # now, and an SMS per stop assigned is expensive noise.
    return notification_type in {
        "booking_confirmed",
        "out_for_delivery",
        "delivery_confirmed",
    }


def _should_send_push(notification_type: str) -> bool:
    # Every customer- and driver-facing lifecycle event. The `*_staff` alerts
    # (`delivery_failed_staff`, `order_placed_staff`, `cash_shortfall_staff`)
    # are intentionally excluded — staff use the dashboard, not the mobile
    # apps that register device tokens. `driver_assigned` isn't here either:
    # the job decides per instance (only a live mid-route addition pushes;
    # the initial batch is covered by one `route_ready`).
    return notification_type in {
        "order_placed",
        "booking_confirmed",
        "out_for_delivery",
        "delivery_confirmed",
        "invoice_generated",
        "route_ready",
    }
