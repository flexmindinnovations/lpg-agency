"""Safe handling of client uploads (OWASP ASVS 12.1 / API4).

Every upload endpoint reads the file through `read_upload`, so size, type and
file-name rules live in one place.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lpg.application.common.errors import ValidationError

if TYPE_CHECKING:
    from fastapi import UploadFile

#: Photos, signatures and scanned documents only.
ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str | None) -> str:
    """The base name only, reduced to `[A-Za-z0-9._-]` and at most 80 chars, so
    it can never add path segments to a storage key."""
    base = (name or "file").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _UNSAFE.sub("_", base).lstrip(".")[:80]
    return cleaned or "file"


async def read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """`(data, safe_name, content_type)`, or `ValidationError` (422)."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        msg = "Upload a JPEG, PNG, WebP or HEIC image, or a PDF."
        raise ValidationError(msg)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        msg = "The file is too large. The limit is 10 MB."
        raise ValidationError(msg)
    if not data:
        msg = "The file is empty."
        raise ValidationError(msg)
    return data, safe_filename(file.filename), content_type
