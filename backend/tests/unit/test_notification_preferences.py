"""Per-agency notification settings (ADR-068): the catalogue metadata, the
override merge and the safety rules for critical events."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import ValidationError
from lpg.application.notification.preferences import (
    ChannelOverride,
    ListNotificationSettingsUseCase,
    ResetNotificationSettingUseCase,
    SetNotificationSettingCommand,
    SetNotificationSettingUseCase,
    effective_channels,
)
from lpg.infrastructure.notification.catalog import SPECS
from lpg.infrastructure.notification.event_catalog import (
    build_event_catalog,
    definition_for,
    meta_types,
)

if TYPE_CHECKING:
    import uuid


class FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[str, ChannelOverride] = {}

    async def list_overrides(self) -> dict[str, ChannelOverride]:
        return dict(self.rows)

    async def get_override(self, notification_type: str) -> ChannelOverride | None:
        return self.rows.get(notification_type)

    async def set_override(
        self, notification_type: str, override: ChannelOverride, updated_by: uuid.UUID | None
    ) -> None:
        del updated_by
        self.rows[notification_type] = override

    async def delete_override(self, notification_type: str) -> None:
        self.rows.pop(notification_type, None)


class FakeUow:
    commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _setting(**kw: bool) -> SetNotificationSettingCommand:
    base = {"in_app": True, "push": False, "sms": False, "email": False}
    return SetNotificationSettingCommand(
        notification_type=kw.pop("notification_type", "order_placed"),  # type: ignore[arg-type]
        **{**base, **kw},
    )


def test_every_catalogue_type_has_settings_metadata() -> None:
    assert set(SPECS) == meta_types()
    assert {d.notification_type for d in build_event_catalog()} == set(SPECS)


def test_defaults_mirror_the_catalogue() -> None:
    d = definition_for("booking_confirmed")
    assert d is not None
    assert (d.default_push, d.default_sms, d.default_email) == (True, True, True)
    assert definition_for("order_placed") is not None
    assert definition_for("order_placed").default_sms is False  # type: ignore[union-attr]


def test_override_wins_and_null_falls_back() -> None:
    d = definition_for("order_placed")
    assert d is not None
    assert effective_channels(d, None).push is True
    assert effective_channels(d, ChannelOverride(push=False)).push is False
    assert effective_channels(d, ChannelOverride(push=None)).push is True


def test_a_critical_event_keeps_its_in_app_alert_even_if_the_row_says_off() -> None:
    d = definition_for("cancellation_requested_staff")
    assert d is not None and d.critical
    assert effective_channels(d, ChannelOverride(in_app=False)).in_app is True


def test_sms_cannot_be_forced_on_where_no_template_exists() -> None:
    d = definition_for("order_placed")
    assert d is not None
    assert effective_channels(d, ChannelOverride(sms=True)).sms is False


@pytest.mark.anyio
async def test_saving_only_stores_what_differs_from_the_default() -> None:
    repo, uow = FakeRepo(), FakeUow()
    use_case = SetNotificationSettingUseCase(repo, uow, build_event_catalog())  # type: ignore[arg-type]
    result = await use_case.execute(_setting(push=False))
    assert result.customized
    assert repo.rows["order_placed"] == ChannelOverride(push=False)
    # Back to the default: the override disappears.
    result = await use_case.execute(_setting(push=True))
    assert not result.customized
    assert repo.rows == {}


@pytest.mark.anyio
async def test_critical_events_reject_switching_in_app_off() -> None:
    use_case = SetNotificationSettingUseCase(FakeRepo(), FakeUow(), build_event_catalog())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await use_case.execute(
            _setting(notification_type="order_cancelled_customer", in_app=False, push=True)
        )


@pytest.mark.anyio
async def test_unavailable_channels_and_unknown_types_are_rejected() -> None:
    use_case = SetNotificationSettingUseCase(FakeRepo(), FakeUow(), build_event_catalog())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await use_case.execute(_setting(sms=True))  # order_placed has no SMS template
    with pytest.raises(ValidationError):
        await use_case.execute(_setting(notification_type="nope"))


@pytest.mark.anyio
async def test_listing_flags_customised_events_and_reset_clears_them() -> None:
    repo, uow = FakeRepo(), FakeUow()
    catalog = build_event_catalog()
    await SetNotificationSettingUseCase(repo, uow, catalog).execute(_setting(push=False))  # type: ignore[arg-type]
    listed = await ListNotificationSettingsUseCase(repo, catalog).execute()  # type: ignore[arg-type]
    by_type = {i.definition.notification_type: i for i in listed}
    assert by_type["order_placed"].customized
    assert not by_type["order_placed"].effective.push
    assert not by_type["booking_confirmed"].customized
    await ResetNotificationSettingUseCase(repo, uow, catalog).execute("order_placed")  # type: ignore[arg-type]
    assert repo.rows == {}
