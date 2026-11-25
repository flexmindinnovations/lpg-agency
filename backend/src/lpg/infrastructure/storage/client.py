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

import asyncio
from typing import TYPE_CHECKING, Any

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from lpg.application.common.errors import ServiceUnavailableError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from types_aiobotocore_s3.client import S3Client

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
        self._connect_lock = asyncio.Lock()

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
        client = await client_cm.__aenter__()
        try:
            try:
                await client.head_bucket(Bucket=self._settings.storage_bucket)
            except ClientError:
                await client.create_bucket(Bucket=self._settings.storage_bucket)
                _logger.info("storage_bucket_created", bucket=self._settings.storage_bucket)
        except Exception:
            await client_cm.__aexit__(None, None, None)
            raise
        self._client = client
        self._client_cm = client_cm

        _logger.info("storage_client_created", bucket=self._settings.storage_bucket)

    async def _ready_client(self) -> S3Client:
        """The connected client, (re)connecting on demand.

        Startup tolerates storage being down or unconfigured (readiness just
        reports it), so the first real upload is where that surfaces. Retry
        the connection here -- storage that was fixed or came up after boot
        then works without a restart -- and turn any failure into a 503 that
        names the cause instead of a bare 500.
        """
        if self._client is not None:
            return self._client
        async with self._connect_lock:
            if self._client is None:
                try:
                    await self.connect()
                except Exception as exc:
                    _logger.error("storage_unavailable", error=str(exc))
                    msg = (
                        "File storage is not available. Ask your administrator to "
                        "check the object storage settings (LPG_STORAGE_*)."
                    )
                    raise ServiceUnavailableError(msg) from exc
        return self.client

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        client = await self._ready_client()
        try:
            return await getattr(client, operation)(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise
            _logger.error("storage_operation_failed", operation=operation, error=str(exc))
            msg = "File storage rejected the request. Check the storage credentials and bucket."
            raise ServiceUnavailableError(msg) from exc
        except BotoCoreError as exc:
            _logger.error("storage_operation_failed", operation=operation, error=str(exc))
            msg = "File storage is unreachable. Check the object storage endpoint settings."
            raise ServiceUnavailableError(msg) from exc

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
        if content_type:
            await self._call(
                "put_object",
                Bucket=self._settings.storage_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        else:
            await self._call("put_object", Bucket=self._settings.storage_bucket, Key=key, Body=data)

    async def download(self, key: str) -> bytes | None:
        try:
            response = await self._call("get_object", Bucket=self._settings.storage_bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return None
            raise
        async with response["Body"] as stream:
            data: bytes = await stream.read()
        return data

    async def delete(self, key: str) -> None:
        await self._call("delete_object", Bucket=self._settings.storage_bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            await self._call("head_object", Bucket=self._settings.storage_bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise
        return True

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        client = await self._ready_client()
        presigned: str = await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.storage_bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
        return presigned


def build_file_storage(settings: Settings | None = None) -> S3CompatibleFileStorage:
    """Construct an S3CompatibleFileStorage from settings."""
    from lpg.config.settings import get_settings

    return S3CompatibleFileStorage(settings or get_settings())
