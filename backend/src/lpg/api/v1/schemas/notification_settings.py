"""Schemas for the per-agency notification settings (ADR-068)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ChannelSetting(BaseModel):
    enabled: bool
    default: bool
    #: False when the channel can't be offered for this event (no SMS template).
    available: bool = True
    #: True when it can't be switched off (critical events keep in-app).
    locked: bool = False


class NotificationEventResponse(BaseModel):
    notification_type: str
    title: str
    description: str
    audience: str
    group: str
    critical: bool
    customized: bool
    in_app: ChannelSetting
    push: ChannelSetting
    sms: ChannelSetting
    email: ChannelSetting


class NotificationSettingsResponse(BaseModel):
    events: list[NotificationEventResponse]


class SetNotificationSettingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app: bool
    push: bool
    sms: bool
    email: bool
