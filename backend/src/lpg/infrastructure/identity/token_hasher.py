"""`Sha256TokenHasher` implements `application/identity/ports.py::TokenHasher`.

Plain SHA-256, deliberately not Argon2 — refresh/reset tokens are already
256-bit cryptographically random values (`secrets.token_urlsafe(32)`), so a
fast hash is the correct tool; Argon2's deliberate slowness exists to defend
low-entropy *passwords* against brute force, which doesn't apply here.
"""

from __future__ import annotations

import hashlib
import hmac


class Sha256TokenHasher:
    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify(self, token: str, token_hash: str) -> bool:
        # Constant-time comparison — an ordinary `==` on the hex digests
        # would let a timing side-channel leak how many leading characters
        # matched, one comparison at a time.
        return hmac.compare_digest(self.hash(token), token_hash)
