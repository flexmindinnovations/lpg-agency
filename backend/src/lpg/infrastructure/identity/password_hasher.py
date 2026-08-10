"""`Argon2PasswordHasher` implements `application/identity/ports.py::PasswordHasher`.

Argon2id per `08-security-architecture.md` §1. Cost parameters come from
`Settings` (`password_argon2_*`), not hardcoded — the right cost is a
function of the host's CPU budget, not a universal constant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import VerifyMismatchError

if TYPE_CHECKING:
    from lpg.config.settings import Settings


class Argon2PasswordHasher:
    def __init__(self, settings: Settings) -> None:
        self._hasher = Argon2(
            time_cost=settings.password_argon2_time_cost,
            memory_cost=settings.password_argon2_memory_cost_kib,
            parallelism=settings.password_argon2_parallelism,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
        # A malformed/foreign hash (`InvalidHash`) is a real data-integrity
        # bug, not "wrong password" — deliberately left to propagate rather
        # than being silently folded into a routine auth failure.

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)
