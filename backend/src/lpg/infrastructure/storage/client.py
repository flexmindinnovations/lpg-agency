"""Concrete ``FileStorage`` (``lpg.application.common.ports.FileStorage``).

S3-compatible object storage — MinIO for every environment that exists
today (local, UAT); a production cloud vendor is deferred with hosting
topology (ADR-022, Phase 3 ADR). Bucket existence is ensured idempotently
on connect, mirroring the ``CREATE EXTENSION IF NOT EXISTS`` pattern the
database migrations already use — a developer running this against a fresh
MinIO volume should never need a manual bucket-creation step.

The client connection is opened once and held for the process lifetime,
the same lifecycle ``Database``/``RedisClient``/``JobQueue`` use, rather
than a fresh ``async with`` per call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from types_aiobotocore_s3.client import S3Client  # type: ignore[import-not-found]

    from lpg.config.settings import Settings

_logger = get_logger(__name__)

_NOT_FOUND_CODES = frozenset({"404", "NoSuchKey"})


class S3CompatibleFileStorage:
    """Implements the ``FileStorage`` port over an S3-compatible client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session()
        self._client_cm: object | None = None
        self._client: S3Client | None = None

    @property
    def client(self) -> S3Client:
        if self._client is None:
            msg = "S3CompatibleFileStorage.connect() has not been called"
            raise RuntimeError(msg)
        return self._client

    async def connect(self) -> None:
        """Open the client connection and ensure the bucket exists."""
        client_cm = self._session.client(
            "s3",
            endpoint_url=self._settings.storage_endpoint_url,
            aws_access_key_id=self._settings.storage_access_key,
            aws_secret_access_key=self._settings.storage_secret_key.get_secret_value(),
            region_name=self._settings.storage_region,
        )
        self._client = await client_cm.__aenter__()
        self._client_cm = client_cm

        try:
            await self._client.head_bucket(Bucket=self._settings.storage_bucket)
        except ClientError:
            await self._client.create_bucket(Bucket=self._settings.storage_bucket)
            _logger.info("storage_bucket_created", bucket=self._settings.storage_bucket)

        _logger.info("storage_client_created", bucket=self._settings.storage_bucket)

    async def disconnect(self) -> None:
        if self._client_cm is not None:
            await self._client_cm.__aexit__(None, None, None)  # type: ignore[attr-defined]
            self._client_cm = None
            self._client = None
            _logger.info("storage_client_closed")

    async def ping(self) -> bool:
        """Return whether the bucket is reachable. Used by readiness."""
        try:
            await self.client.head_bucket(Bucket=self._settings.storage_bucket)
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            _logger.warning("storage_ping_failed", error=str(exc))
            return False
        return True

    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        # Two explicit calls rather than a conditionally-built kwargs dict —
        # `put_object`'s stub types every optional argument individually, so
        # splatting a `dict[str, str]` into it defeats that precision.
        if content_type:
            await self.client.put_object(
                Bucket=self._settings.storage_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        else:
            await self.client.put_object(Bucket=self._settings.storage_bucket, Key=key, Body=data)

    async def download(self, key: str) -> bytes | None:
        try:
            response = await self.client.get_object(Bucket=self._settings.storage_bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return None
            raise
        async with response["Body"] as stream:
            data: bytes = await stream.read()
        return data

    async def delete(self, key: str) -> None:
        await self.client.delete_object(Bucket=self._settings.storage_bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            await self.client.head_object(Bucket=self._settings.storage_bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise
        return True

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        presigned: str = await self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.storage_bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
        return presigned


def build_file_storage(settings: Settings | None = None) -> S3CompatibleFileStorage:
    """Construct an S3CompatibleFileStorage from settings."""
    from lpg.config.settings import get_settings

    return S3CompatibleFileStorage(settings or get_settings())
