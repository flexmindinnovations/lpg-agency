"""Notification endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.notification import get_notification_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.notification import (
    NotificationResponse,
    PaginatedNotificationResponse,
    UnreadCountResponse,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.notification.ports import InAppNotificationRepository
from lpg.application.notification.use_cases import (
    CountUnreadUseCase,
    ListNotificationsUseCase,
    MarkAllReadUseCase,
    MarkReadUseCase,
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
