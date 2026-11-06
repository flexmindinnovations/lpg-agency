"""Profile picture (planning feature 62): the domain rules and the use cases, with
in-memory fakes. Real PostgreSQL / MinIO / tenant-isolation coverage is in
`tests/integration/test_my_profile.py` and the admin endpoint smoke tests."""

from __future__ import annotations

import uuid

import pytest

from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.application.identity.my_profile import (
    MAX_AVATAR_BYTES,
    RemoveMyAvatarCommand,
    RemoveMyAvatarUseCase,
    SetMyAvatarCommand,
    SetMyAvatarUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.identity.user import IdentityUser

TENANT = uuid.uuid4()
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32


def _user(*, tenant: uuid.UUID | None = TENANT, avatar_ref: str | None = None) -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=tenant,
        branch_id=None,
        email="admin@example.com",
        phone_number=None,
        password_hash=None,
        role="agency_admin",
        avatar_ref=avatar_ref,
    )


class _Repository:
    def __init__(self, user: IdentityUser | None, *, fail_save: bool = False) -> None:
        self._user = user
        self._fail_save = fail_save
        self.saved = 0

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        return self._user if self._user is not None and self._user.id == user_id else None

    async def save(self, user: IdentityUser) -> None:
        if self._fail_save:
            msg = "database down"
            raise RuntimeError(msg)
        del user
        self.saved += 1


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str | None]] = {}

    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self.objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class _Audit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def record(self, **entry: object) -> None:
        self.entries.append(entry)


def _set(
    user: IdentityUser | None, storage: _Storage, audit: _Audit, *, fail_save: bool = False
) -> tuple[SetMyAvatarUseCase, _Repository]:
    repository = _Repository(user, fail_save=fail_save)
    return SetMyAvatarUseCase(repository, storage, audit), repository  # type: ignore[arg-type]


class TestDomain:
    def test_a_picture_must_sit_under_the_users_own_agency(self) -> None:
        user = _user()
        user.set_avatar(f"tenant/{TENANT}/avatars/{user.id}/a.jpg")
        assert user.avatar_ref == f"tenant/{TENANT}/avatars/{user.id}/a.jpg"

        with pytest.raises(InvariantViolation):
            user.set_avatar(f"tenant/{uuid.uuid4()}/avatars/{user.id}/a.jpg")
        with pytest.raises(InvariantViolation):
            user.set_avatar(f"tenant/{TENANT}/../tenant/{uuid.uuid4()}/avatars/x.jpg")
        with pytest.raises(InvariantViolation):
            user.set_avatar(f"tenant/{TENANT}/" + "a" * 300)

    def test_a_user_with_no_agency_cannot_have_a_picture(self) -> None:
        with pytest.raises(InvariantViolation):
            _user(tenant=None).set_avatar("tenant/x/a.jpg")

    def test_it_can_be_cleared(self) -> None:
        user = _user(avatar_ref=f"tenant/{TENANT}/a.jpg")
        user.clear_avatar()
        assert user.avatar_ref is None


class TestSetMyAvatar:
    async def test_stores_the_picture_under_the_users_own_prefix_and_audits_it(self) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        use_case, repository = _set(user, storage, audit)

        result = await use_case.execute(
            SetMyAvatarCommand(user_id=user.id, data=PNG, content_type="image/png")
        )

        (key,) = storage.objects
        assert key.startswith(f"tenant/{TENANT}/avatars/{user.id}/")
        assert key.endswith(".png")
        assert storage.objects[key] == (PNG, "image/png")
        assert result.avatar_ref == key
        assert repository.saved == 1
        (entry,) = audit.entries
        assert entry["details"] == {"change": "own_avatar", "avatar": "set"}
        assert key not in str(entry), "the storage key never goes in the audit trail"

    async def test_replacing_deletes_the_previous_picture(self) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        use_case, _ = _set(user, storage, audit)
        await use_case.execute(
            SetMyAvatarCommand(user_id=user.id, data=JPEG, content_type="image/jpeg")
        )
        (first,) = storage.objects

        await use_case.execute(
            SetMyAvatarCommand(user_id=user.id, data=WEBP, content_type="image/webp")
        )

        assert first not in storage.objects
        assert len(storage.objects) == 1
        assert user.avatar_ref in storage.objects

    @pytest.mark.parametrize(
        ("data", "content_type"),
        [
            pytest.param(JPEG, "application/pdf", id="a-pdf"),
            pytest.param(JPEG, "image/svg+xml", id="an-svg"),
            pytest.param(b"", "image/jpeg", id="empty"),
            pytest.param(b"<html>not a picture</html>", "image/jpeg", id="html-as-jpeg"),
            pytest.param(PNG, "image/jpeg", id="png-bytes-as-jpeg"),
            pytest.param(b"\xff\xd8\xff" + b"x" * MAX_AVATAR_BYTES, "image/jpeg", id="too-large"),
        ],
    )
    async def test_refuses_anything_that_is_not_a_picture_and_stores_nothing(
        self, data: bytes, content_type: str
    ) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        use_case, repository = _set(user, storage, audit)

        with pytest.raises(ValidationError):
            await use_case.execute(
                SetMyAvatarCommand(user_id=user.id, data=data, content_type=content_type)
            )

        assert storage.objects == {}
        assert repository.saved == 0
        assert audit.entries == []

    async def test_a_failed_save_does_not_leave_the_upload_behind(self) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        use_case, _ = _set(user, storage, audit, fail_save=True)

        with pytest.raises(RuntimeError):
            await use_case.execute(
                SetMyAvatarCommand(user_id=user.id, data=JPEG, content_type="image/jpeg")
            )

        assert storage.objects == {}
        assert audit.entries == []

    async def test_an_unknown_user_is_not_found(self) -> None:
        storage = _Storage()
        use_case, _ = _set(_user(), storage, _Audit())
        with pytest.raises(NotFoundError):
            await use_case.execute(
                SetMyAvatarCommand(user_id=uuid.uuid4(), data=JPEG, content_type="image/jpeg")
            )
        assert storage.objects == {}


class TestRemoveMyAvatar:
    async def test_removes_the_reference_deletes_the_object_and_audits(self) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        use_case, _ = _set(user, storage, audit)
        await use_case.execute(
            SetMyAvatarCommand(user_id=user.id, data=JPEG, content_type="image/jpeg")
        )
        audit.entries.clear()

        remove = RemoveMyAvatarUseCase(_Repository(user), storage, audit)  # type: ignore[arg-type]
        result = await remove.execute(RemoveMyAvatarCommand(user_id=user.id))

        assert result.avatar_ref is None
        assert storage.objects == {}
        (entry,) = audit.entries
        assert entry["details"] == {"change": "own_avatar", "avatar": "removed"}

    async def test_with_no_picture_it_does_nothing(self) -> None:
        user, storage, audit = _user(), _Storage(), _Audit()
        repository = _Repository(user)

        await RemoveMyAvatarUseCase(repository, storage, audit).execute(  # type: ignore[arg-type]
            RemoveMyAvatarCommand(user_id=user.id)
        )

        assert repository.saved == 0
        assert audit.entries == []
