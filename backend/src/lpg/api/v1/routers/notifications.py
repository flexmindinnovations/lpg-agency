"""Notification endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.notification import (
    get_device_token_repository,
    get_notification_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.notification import (
    NotificationResponse,
    PaginatedNotificationResponse,
    RegisterDeviceRequest,
    UnreadCountResponse,
    UnregisterDeviceRequest,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.notification.ports import (
    DeviceTokenRepository,
    InAppNotificationRepository,
)
from lpg.application.notification.use_cases import (
    CountUnreadUseCase,
    ListNotificationsUseCase,
    MarkAllReadUseCase,
    MarkReadUseCase,
    RegisterDeviceUseCase,
    UnregisterDeviceUseCase,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedNotificationResponse)
async def list_notifications(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repo: Annotated[InAppNotificationRepository, Depends(get_notification_repository)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
) -> PaginatedNotificationResponse:
    """List notifications for the current user."""
    use_case = ListNotificationsUseCase(repo)
    items = await use_case.execute(
        user_id=principal.user_id or uuid.UUID(int=0),
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    return PaginatedNotificationResponse(
        items=[NotificationResponse.model_validate(item) for item in items]
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repo: Annotated[InAppNotificationRepository, Depends(get_notification_repository)],
) -> UnreadCountResponse:
    """Get the unread notification count for the current user."""
    use_case = CountUnreadUseCase(repo)
    count = await use_case.execute(user_id=principal.user_id or uuid.UUID(int=0))
    return UnreadCountResponse(count=count)


@router.patch("/{id}/read", status_code=status.HTTP_200_OK)
async def mark_read(
    id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    repo: Annotated[InAppNotificationRepository, Depends(get_notification_repository)],
) -> None:
    """Mark a specific notification as read."""
    use_case = MarkReadUseCase(uow, repo)
    await use_case.execute(notification_id=id, user_id=principal.user_id or uuid.UUID(int=0))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    repo: Annotated[InAppNotificationRepository, Depends(get_notification_repository)],
) -> None:
    """Mark all notifications as read for the current user."""
    use_case = MarkAllReadUseCase(uow, repo)
    await use_case.execute(user_id=principal.user_id or uuid.UUID(int=0))


@router.post("/devices", status_code=status.HTTP_204_NO_CONTENT)
async def register_device(
    body: RegisterDeviceRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    repo: Annotated[DeviceTokenRepository, Depends(get_device_token_repository)],
) -> None:
    """Register (or refresh) this device's FCM token for push delivery.

    Idempotent — the app calls this on every launch and on token refresh.
    """
    use_case = RegisterDeviceUseCase(uow, repo)
    await use_case.execute(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id or uuid.UUID(int=0),
        token=body.token,
        platform=body.platform,
    )


@router.post("/devices/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    body: UnregisterDeviceRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    repo: Annotated[DeviceTokenRepository, Depends(get_device_token_repository)],
) -> None:
    """Drop this device's token — called on logout. A no-op if the token
    isn't registered (already gone, or never was). RLS scopes the delete to
    the caller's tenant; POST (not DELETE) so the 4 KB token rides in the
    body rather than the URL."""
    use_case = UnregisterDeviceUseCase(uow, repo)
    await use_case.execute(token=body.token)
