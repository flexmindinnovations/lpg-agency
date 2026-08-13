"""`FernetFieldEncryptor` implements `application/customer/ports.py::FieldEncryptor`.

Application-layer (not database-layer) field encryption for the one column
`03-database-schema.md` explicitly documents as "app-layer encrypted":
`customer.kyc_document.doc_reference`. Fernet (AES-128-CBC + HMAC-SHA256,
via `cryptography`, already a transitive dependency of `pyjwt[crypto]`) is
authenticated symmetric encryption — a tampered ciphertext fails to decrypt
rather than silently returning garbage, which a bare AES-CBC implementation
would not catch.

The key is a `Settings.kyc_encryption_key` (see that field's docstring for
the ephemeral-local-only generation rule, mirroring `jwt_private_key`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

if TYPE_CHECKING:
    from lpg.config.settings import Settings


class DecryptionError(Exception):
    """The ciphertext could not be decrypted — wrong key, or it was tampered with."""


class FernetFieldEncryptor:
    def __init__(self, settings: Settings) -> None:
        if settings.kyc_encryption_key is None:
            msg = (
                "kyc_encryption_key is not configured. Every non-local environment "
                "must supply one — see Settings.kyc_encryption_key's docstring."
            )
            raise ValueError(msg)
        self._fernet = Fernet(settings.kyc_encryption_key.get_secret_value().encode("ascii"))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            msg = "KYC document reference could not be decrypted."
            raise DecryptionError(msg) from exc
