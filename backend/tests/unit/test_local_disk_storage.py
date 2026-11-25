"""LocalDiskFileStorage: round trip, compression, traversal, signed links."""

from __future__ import annotations

import io
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image
from pydantic import SecretStr

from lpg.application.common.errors import NotFoundError
from lpg.config.settings import Settings
from lpg.infrastructure.storage.local_disk import COMPRESSED_SUFFIX, LocalDiskFileStorage

if TYPE_CHECKING:
    from pathlib import Path

KEY = "tenant/11111111-1111-1111-1111-111111111111/kyc/abc_photo.jpg"


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskFileStorage:
    settings = Settings(
        environment="local",
        storage_local_dir=str(tmp_path / "uploads"),
        kyc_encryption_key=SecretStr("k" * 44),
    )
    return LocalDiskFileStorage(settings)


def _big_jpeg(width: int = 3200, height: int = 2400) -> bytes:
    image = Image.effect_noise((width, height), 40).convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


async def test_round_trip_and_delete(storage: LocalDiskFileStorage) -> None:
    await storage.connect()
    await storage.upload("tenant/t/a/x.pdf", b"%PDF-1.4 data", content_type="application/pdf")

    assert await storage.download("tenant/t/a/x.pdf") == b"%PDF-1.4 data"
    assert await storage.exists("tenant/t/a/x.pdf")
    assert not (storage.root / f"tenant/t/a/x.pdf{COMPRESSED_SUFFIX}").exists()

    await storage.delete("tenant/t/a/x.pdf")
    assert await storage.download("tenant/t/a/x.pdf") is None
    await storage.delete("tenant/t/a/x.pdf")  # idempotent


async def test_image_keeps_original_and_adds_smaller_capped_copy(
    storage: LocalDiskFileStorage,
) -> None:
    original = _big_jpeg()
    await storage.upload(KEY, original, content_type="image/jpeg")

    assert await storage.download(KEY) == original
    view = await storage.download_view(KEY)
    assert view is not None
    data, content_type = view
    assert content_type == "image/webp"
    assert len(data) < len(original)
    with Image.open(io.BytesIO(data)) as copy:
        assert max(copy.size) <= 1600


async def test_undecodable_image_is_stored_without_copy(storage: LocalDiskFileStorage) -> None:
    await storage.upload(KEY, b"not really an image", content_type="image/heic")

    assert await storage.download(KEY) == b"not really an image"
    view = await storage.download_view(KEY)
    assert view is not None
    assert view[0] == b"not really an image"


@pytest.mark.parametrize(
    "key",
    ["../etc/passwd", "tenant/../../x", "/abs/path", "a//b", "a\\b", "", f"x{COMPRESSED_SUFFIX}"],
)
async def test_bad_keys_are_rejected(storage: LocalDiskFileStorage, key: str) -> None:
    with pytest.raises(NotFoundError):
        await storage.upload(key, b"x")
    with pytest.raises(NotFoundError):
        await storage.download(key)


async def test_signed_url_verifies_and_expires(storage: LocalDiskFileStorage) -> None:
    url = await storage.url(KEY, expires_seconds=60)
    query = parse_qs(urlparse(url).query)
    key, exp, sig = query["key"][0], int(query["exp"][0]), query["sig"][0]

    assert "/files/view?" in url
    assert storage.verify_signature(key, exp, sig)
    assert not storage.verify_signature(key + "x", exp, sig)
    assert not storage.verify_signature(key, exp + 1, sig)
    assert not storage.verify_signature(
        key, int(time.time()) - 5, storage._sign(key, int(time.time()) - 5)
    )


async def test_usage_counts_files(storage: LocalDiskFileStorage) -> None:
    await storage.upload("tenant/t/a.pdf", b"%PDF-1.4 12345", content_type="application/pdf")
    usage = await storage.usage()

    assert usage.file_count == 1
    assert usage.stored_bytes == len(b"%PDF-1.4 12345")
    assert usage.free_bytes > 0
