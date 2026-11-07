"""Schemas for a phone asking about itself (`routers/device_session.py`)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


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
    needs_name: bool = Field(
        default=False,
        description="True when nobody has named this phone yet (it carries the generated "
        "device_<ref> name): the app asks the user once. False for a phone that is already "
        "registered in the agency.",
    )


class NameMyDeviceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            msg = "A phone needs a name."
            raise ValueError(msg)
        return cleaned
