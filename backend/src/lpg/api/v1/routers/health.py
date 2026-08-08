"""Health and readiness endpoints.

The split is deliberate and load-bearing (``12-observability.md`` §5):

* ``/health/live``  — is the process running? Checks **nothing** external.
  A liveness failure tells the platform to **restart the container**.
* ``/health/ready`` — are dependencies reachable? Checks PostgreSQL and Redis.
  A readiness failure tells the platform to **remove this instance from
  rotation** without killing it.

Conflating them is a classic and expensive mistake: if liveness checked the
database, a brief database blip would restart every application instance
simultaneously, turning a recoverable dependency wobble into a full outage.

This module depends only on the application-layer ``HealthCheck`` port, never
on a concrete database or cache client — the composition root supplies the
implementations.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from lpg.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from lpg.application.common.ports import HealthCheck

router = APIRouter(tags=["Health"])


class LivenessResponse(BaseModel):
    """Process is up. Nothing external is consulted."""

    status: Literal["alive"] = "alive"
    app_name: str
    version: str


class DependencyStatus(BaseModel):
    name: str
    healthy: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: list[DependencyStatus] = Field(default_factory=list)


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Returns 200 whenever the process is running. Checks no external "
        "dependency by design — a failure here means the container should be "
        "restarted."
    ),
)
async def liveness(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LivenessResponse:
    return LivenessResponse(app_name=settings.app_name, version=settings.app_version)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Reports whether every dependency required to serve traffic is "
        "reachable. Returns 503 when any dependency is down, so the instance "
        "is removed from rotation without being restarted."
    ),
    responses={503: {"description": "One or more dependencies are unavailable"}},
)
async def readiness(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    from lpg.api.app import get_health_checks

    health_checks: list[HealthCheck] = get_health_checks()
    results: list[DependencyStatus] = []

    async def _evaluate(dependency: HealthCheck) -> DependencyStatus:
        try:
            healthy: bool = await asyncio.wait_for(
                dependency.check(),
                timeout=settings.health_check_timeout_seconds,
            )
        except TimeoutError:
            return DependencyStatus(
                name=dependency.name,
                healthy=False,
                detail=f"timed out after {settings.health_check_timeout_seconds}s",
            )
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            return DependencyStatus(name=dependency.name, healthy=False, detail=str(exc))
        return DependencyStatus(name=dependency.name, healthy=healthy)

    for dependency in health_checks:
        results.append(await _evaluate(dependency))

    # No dependencies registered means the lifespan has not run, so the
    # instance cannot serve traffic. Reporting "ready" after checking nothing
    # would be a false claim to the load balancer.
    all_healthy = bool(results) and all(result.healthy for result in results)
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if all_healthy else "not_ready",
        dependencies=results,
    )
