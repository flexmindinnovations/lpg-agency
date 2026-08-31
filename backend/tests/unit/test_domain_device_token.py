"""Unit tests for the DeviceToken value record."""

import uuid

import pytest

from lpg.domain.notification.device_token import DeviceToken


def _make(**overrides: object) -> DeviceToken:
    kwargs: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "recipient_user_id": uuid.uuid4(),
        "token": "fcm-token-abc",
        "platform": "android",
    }
    kwargs.update(overrides)
    return DeviceToken(**kwargs)  # type: ignore[arg-type]


def test_accepts_known_platforms() -> None:
    for platform in ("android", "ios", "web"):
        assert _make(platform=platform).platform == platform


def test_rejects_unknown_platform() -> None:
    with pytest.raises(ValueError, match="platform"):
        _make(platform="blackberry")


def test_rejects_blank_token() -> None:
    with pytest.raises(ValueError, match="empty"):
        _make(token="   ")


def test_defaults_are_populated() -> None:
    token = _make()
    assert token.id is not None
    assert token.created_at.tzinfo is not None
    assert token.last_seen_at.tzinfo is not None
