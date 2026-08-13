"""Event handlers for the cylinder ledger bounded context."""

import uuid
from typing import Any

from lpg.api.app import get_app_state
from lpg.domain.delivery.route import OrderDelivered
from lpg.domain.order.order import CylinderDelivered
from lpg.infrastructure.persistence.repositories.cylinder_ledger import SqlAlchemyCylinderLedgerRepository
from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lpg.application.cylinder_ledger.use_cases import AppendLedgerTransactionsFromOrderUseCase


async def _handle_order_delivered(event: Any) -> None:
    """Handle both route's OrderDelivered and order's CylinderDelivered."""
    
    # In some architectures, the worker/handler receives the UoW. Here, we must
    # create our own transaction because the domain dispatcher runs post-commit.
    state = get_app_state()
    if not state.database:
        return
        
    # We must mock a minimal tenant context to create the UoW since we are
    # running outside a request. But wait, UnitOfWork requires TenantContext.
    # Let's create a dummy TenantContext or just pass None if allowed.
    # Actually, we can just use the components directly.
    # Since we need to follow the rules, let's use the SqlAlchemyUnitOfWork directly.
    from lpg.application.common.ports import TenantContext
    
    # We create a generic tenant context for the background process
    tenant_context = TenantContext(tenant_id=event.tenant_id, tenant_slug="background")
    
    async for session in state.database.open_session(tenant_id=event.tenant_id):
        # We don't use the event dispatcher inside the handler's UoW (or we could pass the global one)
        uow = SqlAlchemyUnitOfWork(session, tenant_context, event_dispatcher=None)
        
        ledger_repo = SqlAlchemyCylinderLedgerRepository(uow)
        order_repo = SqlAlchemyOrderRepository(uow)
        
        use_case = AppendLedgerTransactionsFromOrderUseCase(ledger_repo, order_repo)
        
        # We need a system or admin user ID for `performed_by`. 
        # Using a nil UUID for system actions.
        system_user_id = uuid.UUID(int=0)
        
        async with uow:
            await use_case.execute(
                tenant_id=event.tenant_id,
                order_id=event.order_id,
                performed_by=system_user_id,
            )
            await uow.commit()


def register_handlers(dispatcher: Any) -> None:
    """Register all cylinder ledger event handlers."""
    # We hook both because they represent the same conceptual transition, just published by different aggregates.
    dispatcher.register(OrderDelivered, _handle_order_delivered)
    dispatcher.register(CylinderDelivered, _handle_order_delivered)
