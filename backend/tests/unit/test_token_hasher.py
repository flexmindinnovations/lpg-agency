"""`Sha256TokenHasher` — no database or Redis required."""

from __future__ import annotations

from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher


class TestHashAndVerify:
    def test_verify_succeeds_for_the_correct_token(self) -> None:
        hasher = Sha256TokenHasher()
        token_hash = hasher.hash("a-raw-token")

        assert hasher.verify("a-raw-token", token_hash)

    def test_verify_fails_for_the_wrong_token(self) -> None:
        hasher = Sha256TokenHasher()
        token_hash = hasher.hash("a-raw-token")

        assert not hasher.verify("a-different-token", token_hash)

    def test_hash_is_deterministic(self) -> None:
        hasher = Sha256TokenHasher()

        assert hasher.hash("a-raw-token") == hasher.hash("a-raw-token")

    def test_hash_output_is_not_the_plaintext(self) -> None:
        hasher = Sha256TokenHasher()

        assert hasher.hash("a-raw-token") != "a-raw-token"
