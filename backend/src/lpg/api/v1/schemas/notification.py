"""Notification API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterDeviceRequest(BaseModel):
    """Body for `POST /notifications/devices` — an FCM registration token
    plus the platform it came from."""

    token: str = Field(min_length=1, max_length=4096)
    platform: Literal["android", "ios", "web"]


class UnregisterDeviceRequest(BaseModel):
    """Body for `DELETE /notifications/devices` — the token to drop."""

    token: str = Field(min_length=1, max_length=4096)


class NotificationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    notification_type: str
    title: str
    body: str
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotificationResponse(BaseModel):
    items: list[NotificationResponse]


class UnreadCountResponse(BaseModel):
    count: int
