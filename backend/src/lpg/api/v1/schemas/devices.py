"""Schemas for a phone asking about itself (`routers/device_session.py`)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MyDeviceResponse(BaseModel):
    control: str = Field(description="The agency's device control mode: off, observe or enforce.")
    status: str | None = Field(
        description="This phone's state (pending, approved, blocked, removed), or null when the "
        "session is not under device control."
    )
    display_name: str | None
    allowed: bool = Field(
        description="Whether the agency lets this phone use the app right now. Under 'observe' "
        "and 'off' this is always true."
    )
