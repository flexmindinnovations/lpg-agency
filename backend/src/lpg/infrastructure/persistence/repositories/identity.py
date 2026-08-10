"""Identity repositories — deliberately **not** built on `SqlAlchemyUnitOfWork`.

Every method here goes through the `SECURITY DEFINER` SQL functions defined
in `migrations/versions/fa52b77ec442_*.py`/`10a62de534be_*.py`, not the ORM
(`IdentityUserModel` etc. exist for future RLS-scoped business-feature
access — e.g. a Phase 7 "list my tenant's users" endpoint — but the
auth-bootstrap paths here never use them). Each method opens its own
short-lived, auto-committing session (`Database.session()`) and calls
exactly one narrowly-scoped function — see `application/identity/login.py`'s
module docstring for why the identity module can't participate in the
normal tenant-scoped `UnitOfWork` the rest of this codebase uses.

A function call in a `FROM` clause always returns exactly one row, even for
a `NULL` composite result (all columns `NULL`) — verified empirically
against a real database, not assumed. Every `_row_to_*` helper below checks
`row.id is not None` to distinguish "no match" from a real row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from lpg.domain.identity.password_reset_token import PasswordResetToken
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import IdentityUser

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping

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

    async def has_permission(self, *, role: str, permission_code: str) -> bool:
        async for session in self._database.session():
            result = await session.execute(
                text("""
                    SELECT 1
                    FROM identity.role_permission rp
                    JOIN identity.role r ON r.id = rp.role_id
                    JOIN identity.permission p ON p.id = rp.permission_id
                    WHERE r.code = :role AND p.code = :permission_code
                """),
                {"role": role, "permission_code": permission_code},
            )
            return result.first() is not None
        return False  # pragma: no cover

    async def get_permission_codes_for_role(self, role: str) -> frozenset[str]:
        async for session in self._database.session():
            result = await session.execute(
                text("""
                    SELECT p.code
                    FROM identity.role_permission rp
                    JOIN identity.role r ON r.id = rp.role_id
                    JOIN identity.permission p ON p.id = rp.permission_id
                    WHERE r.code = :role
                """),
                {"role": role},
            )
            return frozenset(row.code for row in result)
        return frozenset()  # pragma: no cover
