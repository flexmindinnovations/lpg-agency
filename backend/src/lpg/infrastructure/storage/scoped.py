"""A `FileStorage` that can only touch one tenant's keys.

Blob references (`blob_ref`, `file_url`, ...) come back from clients in later
requests, so a crafted reference such as another agency's
`tenant/<other-id>/kyc/...` would otherwise let a caller OCR, download or
get a signed URL for someone else's KYC document (OWASP API1 - BOLA). Every
API-facing use of storage goes through this wrapper, which makes
`tenant/{tenant_id}/` the only reachable prefix; anything else is a 404, the
same answer as a missing object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.application.common.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import FileStorage


class TenantScopedFileStorage:
    def __init__(self, inner: FileStorage, tenant_id: uuid.UUID) -> None:
        self._inner = inner
        self._prefix = f"tenant/{tenant_id}/"

    def _check(self, key: str) -> str:
        if not key.startswith(self._prefix) or ".." in key.split("/"):
            msg = "File not found."
            raise NotFoundError(msg)
        return key

    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        await self._inner.upload(self._check(key), data, content_type=content_type)

    async def download(self, key: str) -> bytes | None:
        return await self._inner.download(self._check(key))

    async def delete(self, key: str) -> None:
        await self._inner.delete(self._check(key))

    async def exists(self, key: str) -> bool:
        return await self._inner.exists(self._check(key))

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return await self._inner.url(self._check(key), expires_seconds=expires_seconds)
