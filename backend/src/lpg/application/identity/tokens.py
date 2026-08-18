"""Shared access+refresh token issuance.

Every path that ends in "issue a fresh token pair" —
`LoginUseCase`, `VerifyOtpUseCase`, `RefreshTokenUseCase` — does it exactly
this way, so it lives in one place rather than three.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from lpg.domain.identity.refresh_token import RefreshToken

if TYPE_CHECKING:
    from lpg.application.identity.ports import (
        JwtSigner,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.domain.identity.user import IdentityUser


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_token_id: uuid.UUID


async def issue_tokens(
    user: IdentityUser,
    *,
    refresh_token_repository: RefreshTokenRepository,
    permission_repository: PermissionRepository,
    token_hasher: TokenHasher,
    jwt_signer: JwtSigner,
    refresh_token_ttl: timedelta,
) -> TokenPair:
    # Embedded in the `scope` claim (`docs/data/17-api-security.md` §4) —
    # fast, no-database-round-trip authorization for standard endpoints via
    # `AuthenticatedPrincipal.permission_codes`. The four high-sensitivity
    # actions (§7) still re-check live against the DB regardless of what's
    # in this claim.
    permission_codes = await permission_repository.get_permission_codes_for_user(user.id)

    access_token = jwt_signer.issue_access_token(
        {
            "sub": str(user.id),
            "name": user.email or user.phone_number or "Unknown User",
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "branch_id": str(user.branch_id) if user.branch_id else None,
            "role": user.role,
            "scope": " ".join(sorted(permission_codes)),
        }
    )

    raw_refresh_token = secrets.token_urlsafe(32)
    refresh_token_id = uuid.uuid4()
    now = datetime.now(UTC)
    refresh_token = RefreshToken(
        refresh_token_id,
        user_id=user.id,
        token_hash=token_hasher.hash(raw_refresh_token),
        issued_at=now,
        expires_at=now + refresh_token_ttl,
    )
    await refresh_token_repository.save(refresh_token)

    return TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        refresh_token_id=refresh_token_id,
    )
