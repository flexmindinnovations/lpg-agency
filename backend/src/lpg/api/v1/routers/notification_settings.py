"""An agency's notification settings per event (ADR-068).

All endpoints need `tenant:configure` (agency admins).

- `GET    /notification-settings`                    — every event with its channels.
- `PUT    /notification-settings/{notification_type}` — set the channels for one event.
- `DELETE /notification-settings/{notification_type}` — back to the defaults.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.notification import (
    get_event_catalog,
    get_notification_preference_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.notification_settings import (
    ChannelSetting,
    NotificationEventResponse,
    NotificationSettingsResponse,
    SetNotificationSettingRequest,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.notification.preferences import (
    EventDefinition,
    EventSetting,
    ListNotificationSettingsUseCase,
    NotificationPreferenceRepository,
    ResetNotificationSettingUseCase,
    SetNotificationSettingCommand,
    SetNotificationSettingUseCase,
)

router = APIRouter(tags=["Notification Settings"])

_PERMISSION = Depends(require_permission("tenant:configure"))


def _to_response(item: EventSetting) -> NotificationEventResponse:
    d, e = item.definition, item.effective
    return NotificationEventResponse(
        notification_type=d.notification_type,
        title=d.title,
        description=d.description,
        audience=d.audience,
        group=d.group,
        critical=d.critical,
        customized=item.customized,
        in_app=ChannelSetting(enabled=e.in_app, default=d.default_in_app, locked=d.critical),
        push=ChannelSetting(enabled=e.push, default=d.default_push),
        sms=ChannelSetting(enabled=e.sms, default=d.default_sms, available=d.supports_sms),
        email=ChannelSetting(enabled=e.email, default=d.default_email, available=d.supports_email),
    )


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    dependencies=[_PERMISSION],
    summary="Every notification event and the channels it uses for this agency",
)
async def list_notification_settings(
    repository: Annotated[
        NotificationPreferenceRepository, Depends(get_notification_preference_repository)
    ],
    catalog: Annotated[list[EventDefinition], Depends(get_event_catalog)],
) -> NotificationSettingsResponse:
    items = await ListNotificationSettingsUseCase(repository, catalog).execute()
    return NotificationSettingsResponse(events=[_to_response(i) for i in items])


@router.put(
    "/notification-settings/{notification_type}",
    response_model=NotificationEventResponse,
    summary="Choose the channels for one event",
    responses={422: {"description": "Unknown event, or a channel this event can't use."}},
)
async def set_notification_setting(
    notification_type: str,
    body: SetNotificationSettingRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[
        NotificationPreferenceRepository, Depends(get_notification_preference_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    catalog: Annotated[list[EventDefinition], Depends(get_event_catalog)],
) -> NotificationEventResponse:
    result = await SetNotificationSettingUseCase(repository, unit_of_work, catalog).execute(
        SetNotificationSettingCommand(
            notification_type=notification_type,
            in_app=body.in_app,
            push=body.push,
            sms=body.sms,
            email=body.email,
            updated_by=principal.user_id,
        )
    )
    return _to_response(result)


@router.delete(
    "/notification-settings/{notification_type}",
    response_model=NotificationEventResponse,
    dependencies=[_PERMISSION],
    summary="Put one event back to its defaults",
)
async def reset_notification_setting(
    notification_type: str,
    repository: Annotated[
        NotificationPreferenceRepository, Depends(get_notification_preference_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    catalog: Annotated[list[EventDefinition], Depends(get_event_catalog)],
) -> NotificationEventResponse:
    result = await ResetNotificationSettingUseCase(repository, unit_of_work, catalog).execute(
        notification_type
    )
    return _to_response(result)
