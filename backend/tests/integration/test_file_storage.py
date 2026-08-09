"""``S3CompatibleFileStorage``, against real MinIO."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.infrastructure.storage.client import S3CompatibleFileStorage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def storage(
    integration_settings: Settings, storage_available: bool
) -> AsyncIterator[S3CompatibleFileStorage]:
    if not storage_available:
        pytest.skip("MinIO is not reachable — start it with ./scripts/dev-up.sh")
    client = S3CompatibleFileStorage(integration_settings)
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()


class TestUploadDownloadDelete:
    async def test_download_returns_none_for_a_missing_key(
        self, storage: S3CompatibleFileStorage
    ) -> None:
        key = f"tenant/{uuid.uuid4()}/missing.txt"

        assert await storage.download(key) is None

    async def test_upload_then_download_round_trips(self, storage: S3CompatibleFileStorage) -> None:
        key = f"tenant/{uuid.uuid4()}/kyc/passport.pdf"
        data = b"%PDF-1.4 not a real pdf, just bytes to round-trip"

        await storage.upload(key, data, content_type="application/pdf")

        assert await storage.download(key) == data

    async def test_delete_removes_the_object(self, storage: S3CompatibleFileStorage) -> None:
        key = f"tenant/{uuid.uuid4()}/delivery/photo.jpg"
        await storage.upload(key, b"jpeg-bytes")

        await storage.delete(key)

        assert await storage.download(key) is None

    async def test_delete_of_a_missing_key_does_not_raise(
        self, storage: S3CompatibleFileStorage
    ) -> None:
        key = f"tenant/{uuid.uuid4()}/never-existed.bin"

        await storage.delete(key)


class TestExists:
    async def test_exists_is_false_for_a_missing_key(
        self, storage: S3CompatibleFileStorage
    ) -> None:
        key = f"tenant/{uuid.uuid4()}/missing.txt"

        assert await storage.exists(key) is False

    async def test_exists_is_true_after_upload(self, storage: S3CompatibleFileStorage) -> None:
        key = f"tenant/{uuid.uuid4()}/signature.png"
        await storage.upload(key, b"png-bytes")

        assert await storage.exists(key) is True


class TestPresignedUrl:
    async def test_url_returns_a_fetchable_link_to_the_uploaded_object(
        self, storage: S3CompatibleFileStorage
    ) -> None:
        import httpx

        key = f"tenant/{uuid.uuid4()}/invoice.pdf"
        data = b"invoice-bytes"
        await storage.upload(key, data)

        link = await storage.url(key, expires_seconds=60)

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(link)
        assert response.status_code == 200
        assert response.content == data


class TestPing:
    async def test_ping_is_true_when_the_bucket_is_reachable(
        self, storage: S3CompatibleFileStorage
    ) -> None:
        assert await storage.ping() is True
