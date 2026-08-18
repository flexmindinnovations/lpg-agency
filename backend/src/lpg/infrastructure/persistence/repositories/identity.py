"""Identity repositories.

`SqlAlchemyIdentityUserRepository`/`SqlAlchemyRefreshTokenRepository`/
`SqlAlchemyPasswordResetTokenRepository` are deliberately **not** built on
`SqlAlchemyUnitOfWork` — every method goes through the `SECURITY DEFINER`
SQL functions defined in `migrations/versions/fa52b77ec442_*.py`/
`10a62de534be_*.py`, not the ORM. Each method opens its own short-lived,
auto-committing session (`Database.session()`) and calls exactly one
narrowly-scoped function — see `application/identity/login.py`'s module
docstring for why the identity module can't participate in the normal
tenant-scoped `UnitOfWork` the rest of this codebase uses.

A function call in a `FROM` clause always returns exactly one row, even for
a `NULL` composite result (all columns `NULL`) — verified empirically
against a real database, not assumed. Every `_row_to_*` helper below checks
`row.id is not None` to distinguish "no match" from a real row.

`SqlAlchemyStaffUserRepository` (Phase 7, bottom of this file) is different:
plain RLS-scoped ORM access against `IdentityUserModel`, no `SECURITY
DEFINER` — see its own docstring for why that's correct for admin-side
staff management specifically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from lpg.domain.identity.password_reset_token import PasswordResetToken
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import IdentityUser
from lpg.infrastructure.persistence.models.identity import IdentityUserModel

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence

    from sqlalchemy.engine import Row

    from lpg.infrastructure.persistence.database import Database


def _row_to_user(row: Row[Any]) -> IdentityUser | None:
    if row.id is None:
        return None
    return IdentityUser(
        row.id,
        tenant_id=row.tenant_id,
        branch_id=row.branch_id,
        email=row.email,
        phone_number=row.phone_number,
        password_hash=row.password_hash,
        role=row.role,
        is_active=row.is_active,
        failed_login_count=row.failed_login_count,
        locked_until=row.locked_until,
        version=row.version,
    )


def _row_to_refresh_token(row: Row[Any]) -> RefreshToken | None:
    if row.id is None:
        return None
    return RefreshToken(
        row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        rotated_at=row.rotated_at,
        revoked_at=row.revoked_at,
        replaced_by_id=row.replaced_by_id,
    )


def _row_to_reset_token(row: Row[Any]) -> PasswordResetToken | None:
    if row.id is None:
        return None
    return PasswordResetToken(
        row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
    )


class SqlAlchemyIdentityUserRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM identity.auth_find_user_by_id(:user_id)"),
                {"user_id": str(user_id)},
            )
            return _row_to_user(result.one())
        return None  # pragma: no cover - session() always yields exactly once

    async def get_by_email(self, email: str) -> IdentityUser | None:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM identity.auth_find_user_by_email(:email)"),
                {"email": email},
            )
            return _row_to_user(result.one())
        return None  # pragma: no cover

    async def get_by_phone_number(
        self, tenant_id: uuid.UUID, phone_number: str
    ) -> IdentityUser | None:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM identity.auth_find_user_by_phone(:tenant_id, :phone)"),
                {"tenant_id": str(tenant_id), "phone": phone_number},
            )
            return _row_to_user(result.one())
        return None  # pragma: no cover

    async def save(self, user: IdentityUser) -> None:
        async for session in self._database.session():
            await session.execute(
                text(
                    "SELECT identity.auth_update_user_auth_state("
                    ":user_id, :failed_login_count, :locked_until, :password_hash"
                    ")"
                ),
                {
                    "user_id": str(user.id),
                    "failed_login_count": user.failed_login_count,
                    "locked_until": user.locked_until,
                    "password_hash": user.password_hash,
                },
            )


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM identity.auth_find_refresh_token_by_hash(:token_hash)"),
                {"token_hash": token_hash},
            )
            return _row_to_refresh_token(result.one())
        return None  # pragma: no cover

    async def save(self, token: RefreshToken) -> None:
        async for session in self._database.session():
            await session.execute(
                text(
                    "SELECT identity.auth_save_refresh_token("
                    ":id, :tenant_id, :user_id, :token_hash, :issued_at, :expires_at, "
                    ":rotated_at, :revoked_at, :replaced_by_id"
                    ")"
                ),
                _refresh_token_params(token),
            )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        async for session in self._database.session():
            await session.execute(
                text("SELECT identity.auth_revoke_all_refresh_tokens_for_user(:user_id)"),
                {"user_id": str(user_id)},
            )


def _refresh_token_params(token: RefreshToken) -> Mapping[str, object]:
    # `tenant_id` isn't part of the `RefreshToken` domain entity (see its
    # module docstring — it carries only what the rotation/reuse-detection
    # invariant needs); the column exists purely for RLS defense-in-depth on
    # direct table access, never read by the auth-bootstrap functions, so
    # `NULL` here is correct, not a gap.
    return {
        "id": str(token.id),
        "tenant_id": None,
        "user_id": str(token.user_id),
        "token_hash": token.token_hash,
        "issued_at": token.issued_at,
        "expires_at": token.expires_at,
        "rotated_at": token.rotated_at,
        "revoked_at": token.revoked_at,
        "replaced_by_id": str(token.replaced_by_id) if token.replaced_by_id else None,
    }


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM identity.auth_find_password_reset_token_by_hash(:token_hash)"),
                {"token_hash": token_hash},
            )
            return _row_to_reset_token(result.one())
        return None  # pragma: no cover

    async def save(self, token: PasswordResetToken) -> None:
        async for session in self._database.session():
            await session.execute(
                text(
                    "SELECT identity.auth_save_password_reset_token("
                    ":id, :tenant_id, :user_id, :token_hash, :expires_at, :used_at"
                    ")"
                ),
                {
                    "id": str(token.id),
                    "tenant_id": None,
                    "user_id": str(token.user_id),
                    "token_hash": token.token_hash,
                    "expires_at": token.expires_at,
                    "used_at": token.used_at,
                },
            )


class SqlAlchemyPermissionRepository:
    """Unlike the three repositories above, `identity.role`/`permission`/
    `role_permission` are Platform-Global (no `tenant_id`, no RLS) — a
    normal query needs no `SECURITY DEFINER` escape hatch.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def has_permission(self, *, user_id: uuid.UUID, permission_code: str) -> bool:
        async for session in self._database.session():
            result = await session.execute(
                text("""
                    SELECT 1
                    FROM identity.identity_user_permission up
                    JOIN identity.permission p ON p.id = up.permission_id
                    WHERE up.user_id = :user_id AND p.code = :permission_code
                """),
                {"user_id": str(user_id), "permission_code": permission_code},
            )
            return result.first() is not None
        return False  # pragma: no cover

    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> frozenset[str]:
        async for session in self._database.session():
            result = await session.execute(
                text("""
                    SELECT p.code
                    FROM identity.identity_user_permission up
                    JOIN identity.permission p ON p.id = up.permission_id
                    WHERE up.user_id = :user_id
                """),
                {"user_id": str(user_id)},
            )
            return frozenset(row.code for row in result)
        return frozenset()  # pragma: no cover

    async def get_all_permission_codes(self) -> frozenset[str]:
        async for session in self._database.session():
            result = await session.execute(
                text("""
                    SELECT code
                    FROM identity.permission
                """)
            )
            return frozenset(row.code for row in result)
        return frozenset()  # pragma: no cover

    async def set_permissions_for_user(self, user_id: uuid.UUID, permission_codes: set[str]) -> None:
        async for session in self._database.session():
            # First, delete all current permissions for the user
            await session.execute(
                text("DELETE FROM identity.identity_user_permission WHERE user_id = :user_id"),
                {"user_id": str(user_id)}
            )
            
            if not permission_codes:
                return
            
            # Insert new permissions
            await session.execute(
                text("""
                    INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
                    SELECT gen_random_uuid(), :user_id, p.id, now()
                    FROM identity.permission p
                    WHERE p.code = ANY(:permission_codes)
                """),
                {"user_id": str(user_id), "permission_codes": list(permission_codes)}
            )


class SqlAlchemyStaffUserRepository:
    """Implements `StaffUserRepository` (`lpg.application.identity.ports`).

    Unlike `SqlAlchemyIdentityUserRepository` above, this is plain
    RLS-scoped ORM access via `Database.session()` — no `SECURITY DEFINER`
    function, matching every other Phase 7 repository's shape. Every use
    case that constructs this repository does so *after* authentication,
    with a resolved tenant already known, so RLS naturally restricts an
    admin to their own tenant's staff — exactly the desired behavior (see
    `StaffUserRepository`'s own docstring for the full rationale).
    """

    def __init__(self, database: Database, tenant_id: uuid.UUID) -> None:
        self._database = database
        self._tenant_id = tenant_id

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        async for session in self._database.session(tenant_id=self._tenant_id):
            row = await session.get(IdentityUserModel, user_id)
            return self._to_domain(row) if row is not None else None
        return None  # pragma: no cover - session() always yields exactly once

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, exclude_roles: frozenset[str]
    ) -> Sequence[IdentityUser]:
        async for session in self._database.session(tenant_id=self._tenant_id):
            result = await session.execute(
                select(IdentityUserModel)
                .where(
                    IdentityUserModel.tenant_id == tenant_id,
                    IdentityUserModel.role.not_in(exclude_roles),
                    IdentityUserModel.is_deleted.is_(False),
                )
                .order_by(IdentityUserModel.email, IdentityUserModel.phone_number)
            )
            return [self._to_domain(row) for row in result.scalars()]
        return []  # pragma: no cover

    async def add(self, user: IdentityUser) -> None:
        """Create the user and materialise their role's permissions.

        `8c221c3e0a91` moved permission resolution from role-based to
        per-user (`identity.identity_user_permission`), and backfilled every
        user that existed at the time — but nothing was added to *create*
        that backfill for a user made afterward. Every path that creates a
        user funnels through this one method (`InviteStaffUserUseCase`, and
        the `EmployeeRegistered` handler in
        `infrastructure/events/tenant_admin_handlers.py`), which is why the
        fix lives here rather than in either caller: a user materialised
        anywhere else in the future gets this automatically, and neither
        caller can forget it.

        Deliberately not a read-time fallback to `role_permission` in
        `SqlAlchemyPermissionRepository`. `PUT /admin/users/{id}/permissions`
        does a full delete-then-insert of a user's *exact* permission set
        (`set_permissions_for_user`) — a fallback would mean an admin
        revoking a role-granted permission for one user, and saving, would
        silently keep granting it from the role. Materialising once at
        creation keeps that editor's contract intact: whatever is in
        `identity_user_permission` for a user *is* their permission set,
        full stop, including a deliberately-emptied one.
        """
        async for session in self._database.session(tenant_id=self._tenant_id):
            session.add(
                IdentityUserModel(
                    id=user.id,
                    tenant_id=user.tenant_id,
                    branch_id=user.branch_id,
                    email=user.email,
                    phone_number=user.phone_number,
                    password_hash=user.password_hash,
                    role=user.role,
                    is_active=user.is_active,
                    failed_login_count=user.failed_login_count,
                    locked_until=user.locked_until,
                )
            )
            # Flush so the FK from identity_user_permission has a row to
            # reference — autoflush is off for this session factory.
            await session.flush()
            await session.execute(
                text("""
                    INSERT INTO identity.identity_user_permission
                        (id, user_id, permission_id, created_at)
                    SELECT gen_random_uuid(), :user_id, rp.permission_id, now()
                    FROM identity.role_permission rp
                    JOIN identity.role r ON r.id = rp.role_id
                    WHERE r.code = :role
                """),
                {"user_id": str(user.id), "role": user.role},
            )

    async def save(self, user: IdentityUser) -> None:
        async for session in self._database.session(tenant_id=self._tenant_id):
            row = await session.get(IdentityUserModel, user.id)
            if row is None:
                msg = f"Cannot save staff user {user.id} — no matching row was loaded."
                raise LookupError(msg)

            row.branch_id = user.branch_id
            row.role = user.role
            row.is_active = user.is_active
            row.password_hash = user.password_hash
            row.failed_login_count = user.failed_login_count
            row.locked_until = user.locked_until

    @staticmethod
    def _to_domain(row: IdentityUserModel) -> IdentityUser:
        return IdentityUser(
            row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            email=row.email,
            phone_number=row.phone_number,
            password_hash=row.password_hash,
            role=row.role,
            is_active=row.is_active,
            failed_login_count=row.failed_login_count,
            locked_until=row.locked_until,
            version=row.version,
        )
