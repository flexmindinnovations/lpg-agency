"""Serving files stored on the server's disk (ADR-068).

Nothing is ever served from a public directory:

* ``GET /files/view`` - the compressed copy of an image (or a PDF as-is), via a
  short-lived HMAC-signed link that ``FileStorage.url()`` put in an API response.
* ``GET /files/download`` - the untouched original, for a signed-in user of the
  same agency.
* ``GET /files/usage`` - disk space for administrators.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import FileStorage
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.infrastructure.storage.local_disk import LocalDiskFileStorage, sniff_content_type

router = APIRouter(prefix="/files", tags=["Files"])

_SAFE_HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"}


class StorageUsageResponse(BaseModel):
    total_bytes: int
    free_bytes: int
    free_percent: float
    stored_bytes: int
    file_count: int
    low_space: bool


def _disk() -> LocalDiskFileStorage:
    from lpg.api.app import get_app_state

    storage = get_app_state().storage
    if storage is None:
        msg = "FileStorage is not configured - the application lifespan has not run."
        raise RuntimeError(msg)
    return storage


@router.get("/view", include_in_schema=False)
async def view_file(
    key: Annotated[str, Query(max_length=600)],
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query(max_length=128)],
) -> Response:
    storage = _disk()
    if not storage.verify_signature(key, exp, sig):
        raise NotFoundError("File not found.")
    found = await storage.download_view(key)
    if found is None:
        raise NotFoundError("File not found.")
    data, content_type = found
    return Response(
        data,
        media_type=content_type,
        headers={**_SAFE_HEADERS, "Cache-Control": "private, max-age=300"},
    )


@router.get("/download")
async def download_original(
    key: Annotated[str, Query(max_length=600)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    _principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> Response:
    """The original, untouched upload. `key` is the `blob_ref` / stored reference."""
    data = await file_storage.download(key)
    if data is None:
        raise NotFoundError("File not found.")
    content_type = sniff_content_type(data)
    name = key.rsplit("/", 1)[-1].split("_", 1)[-1] or "file"
    return Response(
        data,
        media_type=content_type,
        headers={
            **_SAFE_HEADERS,
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )


@router.get(
    "/usage",
    response_model=StorageUsageResponse,
    dependencies=[Depends(require_permission("tenant:configure"))],
)
async def storage_usage() -> StorageUsageResponse:
    """Disk space on the server holding uploads, for the admin to watch."""
    storage = _disk()
    usage = await storage.usage()
    threshold = storage.low_space_percent
    return StorageUsageResponse(
        total_bytes=usage.total_bytes,
        free_bytes=usage.free_bytes,
        free_percent=round(usage.free_percent, 1),
        stored_bytes=usage.stored_bytes,
        file_count=usage.file_count,
        low_space=usage.free_percent < threshold,
    )
