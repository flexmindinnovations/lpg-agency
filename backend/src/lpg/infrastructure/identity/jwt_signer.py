"""`PyJwtSigner` implements `application/identity/ports.py::JwtSigner`.

RS256, per `docs/data/17-api-security.md` §1 (ADR-035). Keys come from
`Settings`; this class never generates or persists a key itself.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import jwt
from jwt import InvalidTokenError

from lpg.application.common.errors import TokenInvalidError

if TYPE_CHECKING:
    from lpg.config.settings import Settings


class PyJwtSigner:
    def __init__(self, settings: Settings) -> None:
        if settings.jwt_private_key is None or settings.jwt_public_key is None:
            msg = (
                "jwt_private_key/jwt_public_key are not configured — see "
                "ADR-035 and .env.dev.example for the expected setup."
            )
            raise RuntimeError(msg)
        self._private_key = settings.jwt_private_key.get_secret_value()
        self._public_key = settings.jwt_public_key
        self._issuer = settings.jwt_issuer
        self._ttl = timedelta(seconds=settings.jwt_access_token_ttl_seconds)

    def issue_access_token(self, claims: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            **claims,
            "iss": self._issuer,
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except InvalidTokenError as exc:
            msg = "Access token is invalid or expired."
            raise TokenInvalidError(msg) from exc
