"""Per-agency notification settings (ADR-068).

The catalogue says what every event does out of the box; an agency can
override the channels per event (in-app, push, SMS, email). An override
column of `None` means "use the default". Who receives a staff event is
still decided by RBAC (the event's permission), edited under Users & roles.

A few events are *critical* — a cancellation waiting for approval, a failed
delivery, a cash shortfall — and keep their in-app alert whatever the
agency chooses, so nothing that needs a person can be silenced entirely.
Delivery OTPs are not notifications at all (they go through the OTP flow).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from lpg.application.common.errors import ValidationError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.application.common.ports import UnitOfWork

CHANNELS = ("in_app", "push", "sms", "email")


@dataclass(frozen=True, slots=True)
class EventDefinition:
    """What the catalogue offers for one event type."""

    notification_type: str
    title: str
    description: str
    #: `customer`, `driver` or `staff`.
    audience: str
    group: str
    default_in_app: bool
    default_push: bool
    default_sms: bool
    default_email: bool
    #: SMS needs a DLT-registered template; email needs a catalogue email.
    supports_sms: bool
    supports_email: bool
    #: In-app cannot be switched off.
    critical: bool = False


@dataclass(frozen=True, slots=True)
class ChannelOverride:
    in_app: bool | None = None
    push: bool | None = None
    sms: bool | None = None
    email: bool | None = None

    @property
    def is_empty(self) -> bool:
        return self.in_app is None and self.push is None and self.sms is None and self.email is None


@dataclass(frozen=True, slots=True)
class EffectiveChannels:
    in_app: bool
    push: bool
    sms: bool
    email: bool

    @property
    def any(self) -> bool:
        return self.in_app or self.push or self.sms or self.email


def defaults_of(definition: EventDefinition) -> EffectiveChannels:
    return EffectiveChannels(
        in_app=definition.default_in_app,
        push=definition.default_push,
        sms=definition.default_sms,
        email=definition.default_email,
    )


def effective_channels(
    definition: EventDefinition, override: ChannelOverride | None
) -> EffectiveChannels:
    base = defaults_of(definition)
    if override is None:
        return base
    return EffectiveChannels(
        in_app=True
        if definition.critical
        else (base.in_app if override.in_app is None else override.in_app),
        push=base.push if override.push is None else override.push,
        sms=(base.sms if override.sms is None else override.sms) and definition.supports_sms,
        email=(base.email if override.email is None else override.email)
        and definition.supports_email,
    )


class NotificationPreferenceRepository(Protocol):
    async def list_overrides(self) -> dict[str, ChannelOverride]: ...

    async def get_override(self, notification_type: str) -> ChannelOverride | None: ...

    async def set_override(
        self, notification_type: str, override: ChannelOverride, updated_by: uuid.UUID | None
    ) -> None: ...

    async def delete_override(self, notification_type: str) -> None: ...


@dataclass(frozen=True, slots=True)
class EventSetting:
    definition: EventDefinition
    effective: EffectiveChannels
    customized: bool


class ListNotificationSettingsUseCase:
    def __init__(
        self, repository: NotificationPreferenceRepository, catalog: Sequence[EventDefinition]
    ) -> None:
        self._repository = repository
        self._catalog = catalog

    async def execute(self) -> list[EventSetting]:
        overrides = await self._repository.list_overrides()
        return [
            EventSetting(
                definition=d,
                effective=effective_channels(d, overrides.get(d.notification_type)),
                customized=d.notification_type in overrides,
            )
            for d in self._catalog
        ]


@dataclass(frozen=True, slots=True)
class SetNotificationSettingCommand:
    notification_type: str
    in_app: bool
    push: bool
    sms: bool
    email: bool
    updated_by: uuid.UUID | None = None


class SetNotificationSettingUseCase:
    """Saves the wanted channels for one event. Stores only what differs
    from the default; setting exactly the defaults clears the override."""

    def __init__(
        self,
        repository: NotificationPreferenceRepository,
        unit_of_work: UnitOfWork,
        catalog: Sequence[EventDefinition],
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._catalog = {d.notification_type: d for d in catalog}

    async def execute(self, command: SetNotificationSettingCommand) -> EventSetting:
        definition = self._catalog.get(command.notification_type)
        if definition is None:
            msg = f"Unknown notification type: {command.notification_type}."
            raise ValidationError(msg)
        if definition.critical and not command.in_app:
            msg = (
                f"“{definition.title}” always shows in the app; "
                "only its other channels can be switched off."
            )
            raise ValidationError(msg)
        if command.sms and not definition.supports_sms:
            msg = f"“{definition.title}” has no SMS template, so SMS can't be turned on."
            raise ValidationError(msg)
        if command.email and not definition.supports_email:
            msg = f"“{definition.title}” has no email version, so email can't be turned on."
            raise ValidationError(msg)

        base = defaults_of(definition)
        wanted = EffectiveChannels(
            in_app=command.in_app, push=command.push, sms=command.sms, email=command.email
        )
        override = ChannelOverride(
            in_app=wanted.in_app if wanted.in_app != base.in_app else None,
            push=wanted.push if wanted.push != base.push else None,
            sms=wanted.sms if wanted.sms != base.sms else None,
            email=wanted.email if wanted.email != base.email else None,
        )
        if override.is_empty:
            await self._repository.delete_override(command.notification_type)
        else:
            await self._repository.set_override(
                command.notification_type, override, command.updated_by
            )
        await self._unit_of_work.commit()
        return EventSetting(
            definition=definition, effective=wanted, customized=not override.is_empty
        )


class ResetNotificationSettingUseCase:
    def __init__(
        self,
        repository: NotificationPreferenceRepository,
        unit_of_work: UnitOfWork,
        catalog: Sequence[EventDefinition],
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._catalog = {d.notification_type: d for d in catalog}

    async def execute(self, notification_type: str) -> EventSetting:
        definition = self._catalog.get(notification_type)
        if definition is None:
            msg = f"Unknown notification type: {notification_type}."
            raise ValidationError(msg)
        await self._repository.delete_override(notification_type)
        await self._unit_of_work.commit()
        return EventSetting(
            definition=definition, effective=defaults_of(definition), customized=False
        )
