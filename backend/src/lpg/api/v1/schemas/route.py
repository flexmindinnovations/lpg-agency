"""Pydantic request/response models for `api/v1/routers/route.py`."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProofOfDeliverySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    otp_verified: bool
    signature_url: str | None = None
    photo_url: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None


class RouteStopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    route_id: uuid.UUID
    order_id: uuid.UUID
    sequence_number: int
    status: str
    failure_reason: str | None = None
    proof_of_delivery: ProofOfDeliverySchema | None = None


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    date: datetime
    status: str
    version: int
    stops: list[RouteStopResponse] = Field(default_factory=list)


class RoutePageResponse(BaseModel):
    items: list[RouteResponse]
    total: int
    page: int
    page_size: int


class PlanRouteRequest(BaseModel):
    branch_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    route_date: datetime | None = None


class AssignOrderRequest(BaseModel):
    order_id: uuid.UUID


class UpdateRouteStatusRequest(BaseModel):
    #: `loaded`/`reconciled` are deliberately excluded — they need
    #: cross-aggregate coordination only `POST .../load` and
    #: `POST .../reconcile` perform; see `UpdateRouteStatusUseCase`'s
    #: docstring.
    status: Literal["in_progress", "cancelled"]


class LoadVehicleLineRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity: int = Field(gt=0)


class LoadVehicleRequest(BaseModel):
    warehouse_id: uuid.UUID
    lines: list[LoadVehicleLineRequest] = Field(min_length=1)
