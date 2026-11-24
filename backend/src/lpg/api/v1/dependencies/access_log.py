"""Read-access logging: who looked at, printed or exported sensitive data.

The generic audit hook records writes only. These dependencies add a record
(structured log line plus an audit-log row) when someone reads data that is
personal or regulated: a customer's KYC documents, GST and sales reports,
printed invoices. The record is made after authorisation succeeds, so a
refused request leaves no entry, and it never raises into the request.
"""

# No `from __future__ import annotations` here on purpose: FastAPI reads the
# parameter annotations of the dependency built below at runtime, and one of
# them refers to a name that only exists inside `access_logged`.

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request

from lpg.api.v1.dependencies.identity import get_security_event_recorder, require_permission
from lpg.application.audit.security_events import SecurityEvent, SecurityEventRecorder
from lpg.application.identity.ports import AuthenticatedPrincipal


async def record_access(
    recorder: SecurityEventRecorder,
    principal: AuthenticatedPrincipal,
    *,
    action: str,
    entity_name: str,
    entity_id: str | None = None,
    entity_display_name: str | None = None,
) -> None:
    await recorder.record(
        SecurityEvent(
            action=action,
            outcome="success",
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            entity_name=entity_name,
            entity_id=entity_id,
            entity_display_name=entity_display_name,
            actor_display_name=getattr(principal, "user_display_name", None),
        )
    )


def access_logged(
    *,
    permission: str,
    action: str,
    entity_name: str,
    path_param: str | None = None,
    label: str | None = None,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """A route dependency. `path_param` names the path parameter holding the
    record's id (e.g. `customer_id`); `label` is the readable name. The caller
    needs `permission`; a refused request is not recorded."""

    require = require_permission(permission)

    async def _dependency(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(require)],
        recorder: Annotated[SecurityEventRecorder, Depends(get_security_event_recorder)],
    ) -> None:
        entity_id = request.path_params.get(path_param) if path_param else None
        await record_access(
            recorder,
            principal,
            action=action,
            entity_name=entity_name,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_display_name=label,
        )

    return _dependency
