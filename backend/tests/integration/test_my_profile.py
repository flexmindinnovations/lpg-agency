"""DA-30: My Profile against real PostgreSQL - own name/phone and own password."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.application.identity.my_profile import (
    ChangeMyPasswordCommand,
    ChangeMyPasswordUseCase,
    GetMyProfileQuery,
    GetMyProfileUseCase,
    RemoveMyAvatarCommand,
    RemoveMyAvatarUseCase,
    SetMyAvatarCommand,
    SetMyAvatarUseCase,
    UpdateMyProfileCommand,
    UpdateMyProfileUseCase,
)
from lpg.application.identity.staff_user import InviteStaffUserCommand, InviteStaffUserUseCase
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyStaffUserRepository,
)
from lpg.infrastructure.storage.scoped import TenantScopedFileStorage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


class _Audit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def record(self, **entry: object) -> None:
        self.entries.append(entry)


class _NoEmail:
    async def send(self, to: str, subject: str, body: str) -> None:
        del to, subject, body


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _staff(database: Database, admin_engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_engine.begin() as conn:
        tenant_id = uuid.UUID(
            str(
                (
                    await conn.execute(
                        text(
                            "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                            "VALUES (gen_random_uuid(), 'Profile Co', :slug, 'ops@example.com') "
                            "RETURNING id"
                        ),
                        {"slug": f"profile-{uuid.uuid4().hex[:10]}"},
                    )
                ).scalar_one()
            )
        )
    user = await InviteStaffUserUseCase(
        SqlAlchemyStaffUserRepository(database, tenant_id),
        SqlAlchemyPasswordResetTokenRepository(database),
        Sha256TokenHasher(),
        _NoEmail(),
        reset_token_ttl=timedelta(hours=1),
    ).execute(
        InviteStaffUserCommand(
            tenant_id=tenant_id, email=f"{uuid.uuid4().hex}@profile.example", role="manager"
        )
    )
    return tenant_id, user.id


async def test_a_user_edits_their_own_name_and_phone(
    database: Database, admin_engine: AsyncEngine
) -> None:
    tenant_id, user_id = await _staff(database, admin_engine)
    repository = SqlAlchemyStaffUserRepository(database, tenant_id)
    audit = _Audit()

    await UpdateMyProfileUseCase(repository, audit).execute(
        UpdateMyProfileCommand(
            user_id=user_id, display_name="  Meena Iyer ", contact_phone="+91 98765 43210"
        )
    )
    profile = await GetMyProfileUseCase(repository).execute(GetMyProfileQuery(user_id=user_id))
    assert (profile.display_name, profile.contact_phone) == ("Meena Iyer", "+91 98765 43210")
    assert audit.entries[0]["after"] == {
        "display_name": "Meena Iyer",
        "contact_phone": "+91 98765 43210",
    }

    with pytest.raises(ValidationError):
        await UpdateMyProfileUseCase(repository, audit).execute(
            UpdateMyProfileCommand(user_id=user_id, display_name="M", contact_phone="call me")
        )


async def test_another_agencys_user_is_invisible(
    database: Database, admin_engine: AsyncEngine
) -> None:
    _tenant_a, user_a = await _staff(database, admin_engine)
    tenant_b, _user_b = await _staff(database, admin_engine)
    with pytest.raises(NotFoundError):
        await GetMyProfileUseCase(SqlAlchemyStaffUserRepository(database, tenant_b)).execute(
            GetMyProfileQuery(user_id=user_a)
        )


class _MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        del content_type
        self.objects[key] = data

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        del expires_seconds
        return f"memory://{key}"


_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


async def test_a_picture_is_kept_replaced_and_removed(
    database: Database, admin_engine: AsyncEngine
) -> None:
    tenant_id, user_id = await _staff(database, admin_engine)
    repository = SqlAlchemyStaffUserRepository(database, tenant_id)
    storage, audit = _MemoryStorage(), _Audit()

    first = await SetMyAvatarUseCase(repository, storage, audit).execute(  # type: ignore[arg-type]
        SetMyAvatarCommand(user_id=user_id, data=_PNG, content_type="image/png")
    )
    reloaded = await repository.get(user_id)
    assert reloaded is not None
    assert reloaded.avatar_ref == first.avatar_ref
    assert (reloaded.avatar_ref or "").startswith(f"tenant/{tenant_id}/avatars/{user_id}/")

    second = await SetMyAvatarUseCase(repository, storage, audit).execute(  # type: ignore[arg-type]
        SetMyAvatarCommand(user_id=user_id, data=_PNG, content_type="image/png")
    )
    assert second.avatar_ref != first.avatar_ref
    assert list(storage.objects) == [second.avatar_ref], "the replaced picture is deleted"

    await RemoveMyAvatarUseCase(repository, storage, audit).execute(  # type: ignore[arg-type]
        RemoveMyAvatarCommand(user_id=user_id)
    )
    after = await repository.get(user_id)
    assert after is not None
    assert after.avatar_ref is None
    assert storage.objects == {}
    assert [entry["details"] for entry in audit.entries] == [
        {"change": "own_avatar", "avatar": "set"},
        {"change": "own_avatar", "avatar": "set"},
        {"change": "own_avatar", "avatar": "removed"},
    ]


async def test_another_agency_cannot_touch_a_users_picture(
    database: Database, admin_engine: AsyncEngine
) -> None:
    tenant_a, user_a = await _staff(database, admin_engine)
    tenant_b, _user_b = await _staff(database, admin_engine)
    storage = _MemoryStorage()
    await SetMyAvatarUseCase(
        SqlAlchemyStaffUserRepository(database, tenant_a),
        storage,  # type: ignore[arg-type]
        _Audit(),
    ).execute(SetMyAvatarCommand(user_id=user_a, data=_PNG, content_type="image/png"))
    (key,) = storage.objects

    # Agency B cannot set or remove agency A's user's picture (RLS: not found),
    # and a failed attempt stores nothing.
    other = SqlAlchemyStaffUserRepository(database, tenant_b)
    with pytest.raises(NotFoundError):
        await SetMyAvatarUseCase(other, storage, _Audit()).execute(  # type: ignore[arg-type]
            SetMyAvatarCommand(user_id=user_a, data=_PNG, content_type="image/png")
        )
    with pytest.raises(NotFoundError):
        await RemoveMyAvatarUseCase(other, storage, _Audit()).execute(  # type: ignore[arg-type]
            RemoveMyAvatarCommand(user_id=user_a)
        )
    assert list(storage.objects) == [key]

    # And agency B's storage view cannot reach agency A's picture at all.
    with pytest.raises(NotFoundError):
        await TenantScopedFileStorage(storage, tenant_b).url(key)  # type: ignore[arg-type]


async def test_password_change_needs_the_current_password(
    database: Database, admin_engine: AsyncEngine, integration_settings: Settings
) -> None:
    tenant_id, user_id = await _staff(database, admin_engine)
    hasher = Argon2PasswordHasher(integration_settings)
    repository = SqlAlchemyStaffUserRepository(database, tenant_id)
    user = await repository.get(user_id)
    assert user is not None
    user.change_password_hash(hasher.hash("first-password-123"))
    await repository.save(user)

    audit = _Audit()
    use_case = ChangeMyPasswordUseCase(repository, hasher, audit, min_length=12)
    with pytest.raises(ValidationError) as wrong:
        await use_case.execute(
            ChangeMyPasswordCommand(
                user_id=user_id, current_password="nope", new_password="second-password-456"
            )
        )
    assert "current_password" in wrong.value.errors
    with pytest.raises(ValidationError) as short:
        await use_case.execute(
            ChangeMyPasswordCommand(
                user_id=user_id, current_password="first-password-123", new_password="short"
            )
        )
    assert "new_password" in short.value.errors

    await use_case.execute(
        ChangeMyPasswordCommand(
            user_id=user_id,
            current_password="first-password-123",
            new_password="second-password-456",
        )
    )
    reloaded = await repository.get(user_id)
    assert reloaded is not None
    assert reloaded.password_hash is not None
    assert hasher.verify("second-password-456", reloaded.password_hash)
    assert audit.entries[0]["action"] == "password_change"
    assert "password" not in str(audit.entries[0]["details"]).replace("own_password", "")
