"""Notification dependencies — composition-root wiring for
`InAppNotificationRepository`.

Same deliberate, narrow exception to "SQLAlchemy stays inside
infrastructure" that every other `dependencies/*.py` module in this
package carries (see the `ignore_imports` entries in `pyproject.toml`):
this is where the API layer is allowed to know concrete infrastructure
types exist, precisely so that `routers/notifications.py` never has to.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import RealtimePublisher, UnitOfWork
from lpg.application.notification.ports import (
    DeviceTokenRepository,
    InAppNotificationRepository,
)


def get_notification_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InAppNotificationRepository:
    from lpg.infrastructure.persistence.repositories.notification import (
        SqlAlchemyInAppNotificationRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    assert isinstance(unit_of_work, SqlAlchemyUnitOfWork)
    return SqlAlchemyInAppNotificationRepository(unit_of_work.session)


def get_device_token_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DeviceTokenRepository:
    from lpg.infrastructure.persistence.repositories.notification import (
        SqlAlchemyDeviceTokenRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    assert isinstance(unit_of_work, SqlAlchemyUnitOfWork)
    return SqlAlchemyDeviceTokenRepository(unit_of_work.session)


def get_realtime_publisher() -> RealtimePublisher | None:
    """The process's Redis publisher, or None before the lifespan ran
    (tests building the app without Redis) — publishing is best-effort."""
    from lpg.api.app import get_app_state

    return get_app_state().realtime_publisher
