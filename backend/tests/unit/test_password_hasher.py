"""`Argon2PasswordHasher` — no database or Redis required."""

from __future__ import annotations

from lpg.config.settings import Settings
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher


def _hasher() -> Argon2PasswordHasher:
    settings = Settings(
        environment="local",
        password_argon2_time_cost=1,
        password_argon2_memory_cost_kib=8,
        password_argon2_parallelism=1,
    )
    return Argon2PasswordHasher(settings)


class TestHashAndVerify:
    def test_verify_succeeds_for_the_correct_password(self) -> None:
        hasher = _hasher()
        password_hash = hasher.hash("correct horse battery staple")

        assert hasher.verify("correct horse battery staple", password_hash)

    def test_verify_fails_for_the_wrong_password(self) -> None:
        hasher = _hasher()
        password_hash = hasher.hash("correct horse battery staple")

        assert not hasher.verify("wrong password", password_hash)

    def test_hash_output_is_not_the_plaintext(self) -> None:
        hasher = _hasher()

        assert hasher.hash("hunter2") != "hunter2"

    def test_hashing_the_same_password_twice_yields_different_hashes(self) -> None:
        hasher = _hasher()

        assert hasher.hash("hunter2") != hasher.hash("hunter2")


class TestNeedsRehash:
    def test_a_freshly_hashed_password_does_not_need_rehashing(self) -> None:
        hasher = _hasher()
        password_hash = hasher.hash("hunter2")

        assert not hasher.needs_rehash(password_hash)

    def test_a_hash_from_weaker_parameters_needs_rehashing(self) -> None:
        weak_settings = Settings(
            environment="local",
            password_argon2_time_cost=1,
            password_argon2_memory_cost_kib=8,
            password_argon2_parallelism=1,
        )
        weak_hasher = Argon2PasswordHasher(weak_settings)
        password_hash = weak_hasher.hash("hunter2")

        strong_settings = Settings(
            environment="local",
            password_argon2_time_cost=3,
            password_argon2_memory_cost_kib=19_456,
            password_argon2_parallelism=1,
        )
        strong_hasher = Argon2PasswordHasher(strong_settings)

        assert strong_hasher.needs_rehash(password_hash)
