"""Notification jobs."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from lpg.domain.notification.in_app_notification import InAppNotification
from lpg.domain.notification.notification_log import NotificationLog

_logger = structlog.get_logger(__name__)

_STAFF_ALERT_ROLES = frozenset({"agency_admin", "branch_manager", "dispatcher"})


async def send_notification(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """ARQ job to process and send a notification.
    
    Payload format:
    {
        "type": "booking_confirmed" | "driver_assigned" | "out_for_delivery" | 
                "delivery_confirmed" | "invoice_generated" | "delivery_failed_staff",
        "tenant_id": str,
        "order_id": str,
        # plus additional context fields like customer_id, branch_id, route_stop_id
    }
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), 
        job_name="send_notification", 
        tenant_id=payload.get("tenant_id")
    )
    
    tenant_id = uuid.UUID(payload["tenant_id"])
    notification_type = payload["type"]
    
    # Imports inside the job to avoid circular dependencies
    from lpg.infrastructure.persistence.database import Database
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
    
    database: Database = ctx["database"]
    
    async for session in database.open_session(tenant_id=tenant_id):
        tenant_context = RequestTenantContext(tenant_id=tenant_id)
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            from lpg.infrastructure.persistence.repositories.notification import (
                SqlAlchemyInAppNotificationRepository,
                SqlAlchemyNotificationLogRepository,
            )
            from lpg.infrastructure.persistence.repositories.identity import (
                SqlAlchemyIdentityUserRepository,
            )
            from lpg.infrastructure.persistence.repositories.customer import (
                SqlAlchemyCustomerRepository,
            )
            from lpg.infrastructure.persistence.repositories.employee import (
                SqlAlchemyEmployeeRepository,
            )
            from lpg.infrastructure.notification.staff_resolver import (
                EmployeeBranchStaffResolver,
            )
            from lpg.infrastructure.channels.email_channel import StubEmailChannel
            from lpg.infrastructure.channels.sms_channel import StubSmsChannel
            
            from lpg.infrastructure.persistence.encryption import AESGCMFieldEncryptor  # type: ignore[import-untyped]
            from lpg.core.config import settings  # type: ignore[import-untyped]
            field_encryptor = AESGCMFieldEncryptor(settings.encryption_key.get_secret_value())
            
            in_app_repo = SqlAlchemyInAppNotificationRepository(session)
            log_repo = SqlAlchemyNotificationLogRepository(session)
            identity_repo = SqlAlchemyIdentityUserRepository(database)
            
            # Resolve recipients
            recipient_user_ids: list[uuid.UUID] = []
            
            if notification_type == "delivery_failed_staff":
                branch_id = uuid.UUID(payload["branch_id"])
                employee_repo = SqlAlchemyEmployeeRepository(uow)
                resolver = EmployeeBranchStaffResolver(employee_repo, identity_repo)
                recipient_user_ids = await resolver.resolve_for_branch(
                    tenant_id=tenant_id, 
                    branch_id=branch_id, 
                    eligible_roles=_STAFF_ALERT_ROLES
                )
            else:
                customer_id = uuid.UUID(payload["customer_id"])
                customer_repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = await customer_repo.get_by_id(customer_id)
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
            
            _logger.info("notification_job_completed", recipients_count=len(recipient_user_ids))


def _get_title(notification_type: str) -> str:
    titles = {
        "booking_confirmed": "Order Confirmed",
        "driver_assigned": "Driver Assigned",
        "out_for_delivery": "Out for Delivery",
        "delivery_confirmed": "Delivery Confirmed",
        "invoice_generated": "Invoice Generated",
        "delivery_failed_staff": "Delivery Failed Alert",
    }
    return titles.get(notification_type, "Notification")


def _get_body(notification_type: str, payload: dict[str, Any]) -> str:
    order_id_short = payload.get("order_id", "Unknown")[:8].upper()
    if notification_type == "booking_confirmed":
        return f"Your order #{order_id_short} has been confirmed."
    elif notification_type == "driver_assigned":
        return f"A driver has been assigned to your order #{order_id_short}."
    elif notification_type == "out_for_delivery":
        return f"Your order #{order_id_short} is out for delivery."
    elif notification_type == "delivery_confirmed":
        return f"Your order #{order_id_short} has been delivered successfully."
    elif notification_type == "invoice_generated":
        return f"An invoice has been generated for your order #{order_id_short}."
    elif notification_type == "delivery_failed_staff":
        return f"Delivery failed for order #{order_id_short}. Please check the system."
    return "You have a new notification."


def _should_send_email(notification_type: str) -> bool:
    return notification_type in {"booking_confirmed", "delivery_confirmed", "invoice_generated"}


def _should_send_sms(notification_type: str) -> bool:
    return notification_type in {"booking_confirmed", "driver_assigned", "out_for_delivery", "delivery_confirmed"}
