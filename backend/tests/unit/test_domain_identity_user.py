"""`IdentityUser`/`RefreshToken` domain aggregates — no database required."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import (
    IdentityUser,
    IdentityUserLocked,
    IdentityUserLoggedIn,
    IdentityUserLoginFailed,
    IdentityUserRoleChanged,
)


def _make_user(**overrides: object) -> IdentityUser:
    defaults: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "branch_id": None,
        "email": "staff@example.com",
        "phone_number": None,
        "password_hash": "argon2-hash",
        "role": "manager",
    }
    defaults.update(overrides)
    return IdentityUser(uuid.uuid4(), **defaults)  # type: ignore[arg-type]


class TestRecordSuccessfulLogin:
    def test_resets_failure_count_and_clears_lock(self) -> None:
        user = _make_user(
            failed_login_count=3, locked_until=datetime.now(UTC) + timedelta(minutes=5)
        )

        user.record_successful_login()

        assert user.failed_login_count == 0
        assert user.locked_until is None

    def test_records_logged_in_event(self) -> None:
        user = _make_user()

        user.record_successful_login()

        assert [type(e) for e in user.events] == [IdentityUserLoggedIn]


class TestRecordFailedLogin:
    def test_increments_failure_count(self) -> None:
        user = _make_user()

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )

        assert user.failed_login_count == 1

    def test_records_login_failed_event(self) -> None:
        user = _make_user()

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )

        assert [type(e) for e in user.events] == [IdentityUserLoginFailed]

    def test_locks_account_once_threshold_is_crossed(self) -> None:
        user = _make_user(failed_login_count=4)

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )

        assert user.is_locked()
        event_types = [type(e) for e in user.events]
        assert IdentityUserLocked in event_types

    def test_does_not_lock_before_threshold(self) -> None:
        user = _make_user(failed_login_count=1)

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )

        assert not user.is_locked()

    def test_does_not_extend_lock_on_further_failures_once_already_locked(self) -> None:
        user = _make_user(
            failed_login_count=5, locked_until=datetime.now(UTC) + timedelta(minutes=1)
        )
        original_lock = user.locked_until

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )

        assert user.locked_until == original_lock


class TestChangePasswordHash:
    def test_replaces_the_hash(self) -> None:
        user = _make_user(password_hash="old-hash")

        user.change_password_hash("new-hash")

        assert user.password_hash == "new-hash"

    def test_rejects_an_empty_hash(self) -> None:
        user = _make_user()

        with pytest.raises(InvariantViolation):
            user.change_password_hash("")


class TestActivateDeactivate:
    def test_deactivate_then_activate_round_trips(self) -> None:
        user = _make_user()

        user.deactivate()
        assert user.is_active is False

        user.activate()
        assert user.is_active is True


class TestChangeRole:
    def test_changes_the_role_and_records_an_event(self) -> None:
        user = _make_user(role="manager")

        user.change_role("agency_admin")

        assert user.role == "agency_admin"
        assert [type(e) for e in user.events] == [IdentityUserRoleChanged]

    def test_rejects_an_unrecognized_role(self) -> None:
        user = _make_user(role="manager")

        with pytest.raises(InvariantViolation):
            user.change_role("made_up_role")

    def test_the_event_carries_the_old_and_new_role(self) -> None:
        user = _make_user(role="manager")

        user.change_role("dispatcher")

        (event,) = user.events
        assert isinstance(event, IdentityUserRoleChanged)
        assert event.old_role == "manager"
        assert event.new_role == "dispatcher"

    @pytest.mark.parametrize(
        "role",
        [
            "super_admin",
            "agency_admin",
            "manager",
            "warehouse_staff",
            "dispatcher",
            "accountant",
            "driver",
            "customer",
        ],
    )
    def test_accepts_every_role_in_the_platform_catalog(self, role: str) -> None:
        user = _make_user(role="manager")

        user.change_role(role)

        assert user.role == role


def _make_refresh_token(**overrides: object) -> RefreshToken:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "token_hash": "sha256-hash",
        "issued_at": now,
        "expires_at": now + timedelta(days=30),
    }
    defaults.update(overrides)
    return RefreshToken(uuid.uuid4(), **defaults)  # type: ignore[arg-type]


class TestRefreshTokenRotate:
    def test_marks_rotated_and_records_replacement(self) -> None:
        token = _make_refresh_token()
        replacement_id = uuid.uuid4()

        token.rotate(replacement_id)

        assert token.rotated_at is not None
        assert token.replaced_by_id == replacement_id
        assert not token.is_usable()

    def test_rotating_twice_raises(self) -> None:
        token = _make_refresh_token()
        token.rotate(uuid.uuid4())

        with pytest.raises(InvariantViolation):
            token.rotate(uuid.uuid4())

    def test_rotating_a_revoked_token_raises(self) -> None:
        token = _make_refresh_token()
        token.revoke()

        with pytest.raises(InvariantViolation):
            token.rotate(uuid.uuid4())


class TestRefreshTokenRevoke:
    def test_marks_revoked(self) -> None:
        token = _make_refresh_token()

        token.revoke()

        assert token.revoked_at is not None
        assert not token.is_usable()

    def test_revoking_twice_is_a_no_op(self) -> None:
        token = _make_refresh_token()
        token.revoke()
        first_revoked_at = token.revoked_at

        token.revoke()

        assert token.revoked_at == first_revoked_at


class TestRefreshTokenExpiry:
    def test_is_expired_when_past_expiry(self) -> None:
        token = _make_refresh_token(expires_at=datetime.now(UTC) - timedelta(seconds=1))

        assert token.is_expired()
        assert not token.is_usable()

    def test_is_usable_before_expiry(self) -> None:
        token = _make_refresh_token()

        assert token.is_usable()
