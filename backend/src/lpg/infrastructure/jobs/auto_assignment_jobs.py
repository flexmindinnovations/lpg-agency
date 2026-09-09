"""Zero-click driver auto-assignment — the `auto_assign_driver` ARQ job.

Triggered by `infrastructure/events/auto_assignment_handlers.py` on
`BookingConfirmed`. Tenant-scoped, idempotent, retry-safe, per the
contract every job in this codebase must satisfy (`infrastructure/jobs/
worker.py`'s own module docstring). See the approved plan (order-to-
delivery fulfillment automation) for the full design rationale, including
why this deliberately overrides this project's own "advisory only, human
confirms" guardrail principle (ADR-045; `planning/features/21-ai-
foundation/PLAN.md` §5; `planning/features/23-ai-assistive-interfaces/
PLAN.md`) — and the mitigations shipped instead: an opt-in, default-off
kill switch; a fixed, auditable system-actor attribution; a Postgres
advisory lock against the concurrent-driver race (no real optimistic-
concurrency exists at the ORM layer to reuse — verified, not assumed);
and a safe no-op on every "someone/something beat us to it" path, never
an error, never a stuck order.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from lpg.application.common.config import is_truthy_config_value
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.delivery.auto_assignment import (
    SuggestDriverAndVehicleForOrderQuery,
    SuggestDriverAndVehicleForOrderUseCase,
)
from lpg.application.order.use_cases import AssignOrderCommand, AssignOrderUseCase
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
from lpg.infrastructure.persistence.repositories.inventory import (
    SqlAlchemyInventoryLocationRepository,
)
from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
from lpg.infrastructure.persistence.repositories.route import SqlAlchemyRouteRepository
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
)
from lpg.infrastructure.persistence.repositories.vehicle import SqlAlchemyVehicleRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: A fixed, well-known actor id for every mutation this job makes — no
#: corresponding `identity.user` row exists or is needed (no FK constraint
#: on `changed_by`/`AuditLogModel.actor_id`, confirmed directly against the
#: models). `user_display_name` below is what actually shows up as the
#: audit-log actor's name, with zero frontend change — this is the primary
#: "how does a dispatcher see the system did this, not a human" answer.
AUTO_ASSIGNMENT_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-0000000a0710")
AUTO_ASSIGNMENT_ACTOR_DISPLAY_NAME = "System (Auto-Assignment)"


async def auto_assign_driver(ctx: dict[str, Any], *, tenant_id: str, order_id: str) -> None:
    """Assigns the best-available driver/vehicle to a just-confirmed order,
    calling the exact same `AssignOrderUseCase` a human's click would use.

    Every exit path below is a safe no-op — the order is left exactly as
    reachable as it was before this job ran (`confirmed`, ready for the
    existing manual assign flow), never partially mutated, never stuck.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="auto_assign_driver", tenant_id=tenant_id
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]
    tenant_uuid = uuid.UUID(tenant_id)
    order_uuid = uuid.UUID(order_id)

    async for session in database.open_session(tenant_id=tenant_uuid):
        tenant_context = RequestTenantContext(
            tenant_id=tenant_uuid,
            user_id=AUTO_ASSIGNMENT_ACTOR_ID,
            user_display_name=AUTO_ASSIGNMENT_ACTOR_DISPLAY_NAME,
        )
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            config_repo = SqlAlchemyTenantConfigurationRepository(uow)
            config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
                GetEffectiveTenantConfigurationQuery(
                    tenant_id=tenant_uuid, config_key="auto_assignment_enabled"
                )
            )
            if config is None or not is_truthy_config_value(config.config_value):
                _logger.info("auto_assignment_disabled_skip", order_id=order_id)
                return

            order_repo = SqlAlchemyOrderRepository(uow)
            order = await order_repo.get_by_id(order_uuid)
            # A human already assigned it (or cancelled it) before this job
            # ran — the second idempotency layer, and the direct answer to
            # "what if a human beats the automation to it." Never an error.
            if order is None or order.status != "confirmed":
                _logger.info(
                    "auto_assignment_noop_wrong_state",
                    order_id=order_id,
                    status=order.status if order is not None else None,
                )
                return

            driver_repo = SqlAlchemyDriverRepository(uow)
            vehicle_repo = SqlAlchemyVehicleRepository(uow)
            route_repo = SqlAlchemyRouteRepository(uow)
            suggestion = await SuggestDriverAndVehicleForOrderUseCase(
                order_repo, driver_repo, vehicle_repo, route_repo
            ).execute(SuggestDriverAndVehicleForOrderQuery(order_id=order_uuid))

            if suggestion is None:
                _logger.info("auto_assignment_no_eligible_candidate", order_id=order_id)
                await job_queue.enqueue(
                    "send_notification",
                    {
                        "type": "order_unassignable_staff",
                        "tenant_id": tenant_id,
                        "order_id": order_id,
                    },
                    _job_id=f"order_unassignable_{order_id}",
                )
                return

            # Serializes concurrent auto-assign jobs racing for the same
            # driver — `pg_advisory_xact_lock` is scoped to this
            # transaction only, auto-released on commit/rollback, no new
            # table/cleanup needed. Necessary because no real optimistic-
            # concurrency exists at the ORM layer to catch this instead
            # (verified: no model sets `version_id_col`, no
            # `with_for_update` anywhere in this codebase).
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:driver_id))"),
                {"driver_id": str(suggestion.driver_id)},
            )
            # Re-check freshness inside the lock — another concurrent job
            # may have just assigned this exact driver to a different
            # order while we were computing the suggestion above.
            still_idle = await route_repo.get_active_route_for_driver(suggestion.driver_id)
            if still_idle is not None:
                _logger.info(
                    "auto_assignment_driver_taken_by_concurrent_job",
                    order_id=order_id,
                    driver_id=str(suggestion.driver_id),
                )
                return

            inventory_repo = SqlAlchemyInventoryLocationRepository(uow)
            assign_use_case = AssignOrderUseCase(order_repo, route_repo, inventory_repo, uow)
            await assign_use_case.execute(
                AssignOrderCommand(
                    order_id=order_uuid,
                    driver_id=suggestion.driver_id,
                    vehicle_id=suggestion.vehicle_id,
                    changed_by=AUTO_ASSIGNMENT_ACTOR_ID,
                )
            )
            _logger.info(
                "auto_assignment_succeeded",
                order_id=order_id,
                driver_id=str(suggestion.driver_id),
                vehicle_id=str(suggestion.vehicle_id),
            )
