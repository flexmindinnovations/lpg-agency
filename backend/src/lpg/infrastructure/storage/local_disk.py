"""Concrete ``FileStorage`` on the server's own disk (ADR-068).

Every agency runs on its own server, so uploads (KYC documents, delivery
photos and signatures, scale certificates, avatars, ...) live in a directory
on that server (``LPG_STORAGE_LOCAL_DIR``), mounted as a persistent Docker
volume so a deploy never wipes it. No third-party object store, no secrets.

Layout: the storage key *is* the relative path (``tenant/<id>/kyc/<uuid>_a.jpg``).

* The **original** is stored byte-for-byte at ``<key>``.
* For raster images a **compressed copy** (long edge capped, WebP) is stored
  next to it at ``<key>.cmp.webp``. Lists, thumbnails and in-page views use the
  compressed copy; the authenticated download endpoint returns the original.
  PDFs (and anything Pillow cannot decode, e.g. HEIC) are stored as-is.

Files are never served by a static route: ``url()`` returns a short-lived,
HMAC-signed link to ``GET /api/v1/files/view``, and the original comes from the
authenticated ``GET /api/v1/files/download``.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from lpg.application.common.errors import NotFoundError, ServiceUnavailableError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.config.settings import Settings

_logger = get_logger(__name__)

COMPRESSED_SUFFIX = ".cmp.webp"
_NO_COMPRESS = frozenset({"application/pdf"})


@dataclass(frozen=True, slots=True)
class DiskUsage:
    total_bytes: int
    free_bytes: int
    stored_bytes: int
    file_count: int

    @property
    def free_percent(self) -> float:
        return 100.0 * self.free_bytes / self.total_bytes if self.total_bytes else 0.0


def sniff_content_type(data: bytes) -> str:
    """Content type from magic bytes (the upload type is not persisted)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"mif1", b"heif", b"hevc"}:
        return "image/heic"
    return "application/octet-stream"


def _compress_image(data: bytes, max_px: int, quality: int) -> bytes | None:
    """WebP copy with the long edge capped at ``max_px``; ``None`` if undecodable."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            out = io.BytesIO()
            image.save(out, format="WEBP", quality=quality, method=4)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


class LocalDiskFileStorage:
    """Implements the ``FileStorage`` port over a local directory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = Path(settings.storage_local_dir).expanduser().resolve()

    @property
    def low_space_percent(self) -> int:
        return self._settings.storage_low_space_percent

    @property
    def root(self) -> Path:
        return self._root

    # -- lifecycle -------------------------------------------------------

    async def connect(self) -> None:
        """Create the directory and prove it is writable."""
        await asyncio.to_thread(self._ensure_writable)
        _logger.info("storage_ready", directory=str(self._root))

    def _ensure_writable(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        probe = self._root / f".write-test-{uuid.uuid4().hex}"
        probe.write_bytes(b"ok")
        probe.unlink()

    async def disconnect(self) -> None:
        return None

    async def ping(self) -> bool:
        """Whether the upload directory is writable. Used by readiness."""
        try:
            await asyncio.to_thread(self._ensure_writable)
        except OSError as exc:
            _logger.warning("storage_ping_failed", error=str(exc))
            return False
        usage = await self.usage_cached()
        if usage is not None and usage.free_percent < self._settings.storage_low_space_percent:
            _logger.warning(
                "storage_low_disk_space",
                free_percent=round(usage.free_percent, 1),
                free_bytes=usage.free_bytes,
            )
        return True

    # -- keys -> paths ---------------------------------------------------

    def _path(self, key: str) -> Path:
        parts = key.split("/")
        bad = (
            not key
            or "\x00" in key
            or "\\" in key
            or key.endswith(COMPRESSED_SUFFIX)
            or any(p in ("", ".", "..") for p in parts)
        )
        if bad:
            raise NotFoundError("File not found.")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise NotFoundError("File not found.")
        return path

    @staticmethod
    def _compressed_of(path: Path) -> Path:
        return path.with_name(path.name + COMPRESSED_SUFFIX)

    # -- FileStorage -----------------------------------------------------

    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(self._write, path, data, content_type)
        except OSError as exc:
            _logger.error("storage_write_failed", error=str(exc))
            msg = "File storage is not available. Ask your administrator to check the server disk."
            raise ServiceUnavailableError(msg) from exc

    def _write(self, path: Path, data: bytes, content_type: str | None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, data)
        compressed_path = self._compressed_of(path)
        kind = (content_type or sniff_content_type(data)).lower()
        compressed = None
        if kind.startswith("image/") and kind not in _NO_COMPRESS:
            compressed = _compress_image(
                data, self._settings.storage_image_max_px, self._settings.storage_image_quality
            )
        # Keep the copy only when it is actually smaller than the original.
        if compressed is not None and len(compressed) < len(data):
            self._atomic_write(compressed_path, compressed)
        else:
            compressed_path.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    async def download(self, key: str) -> bytes | None:
        """The original bytes."""
        return await self._read(self._path(key))

    async def download_view(self, key: str) -> tuple[bytes, str] | None:
        """The compressed copy when there is one, else the original, plus its type."""
        path = self._path(key)
        data = await self._read(self._compressed_of(path))
        if data is not None:
            return data, "image/webp"
        data = await self._read(path)
        return None if data is None else (data, sniff_content_type(data))

    @staticmethod
    async def _read(path: Path) -> bytes | None:
        try:
            return await asyncio.to_thread(path.read_bytes)
        except (FileNotFoundError, IsADirectoryError):
            return None

    async def delete(self, key: str) -> None:
        path = self._path(key)

        def _remove() -> None:
            path.unlink(missing_ok=True)
            self._compressed_of(path).unlink(missing_ok=True)

        await asyncio.to_thread(_remove)

    async def exists(self, key: str) -> bool:
        path = self._path(key)
        return await asyncio.to_thread(path.is_file)

    # -- signed view links -----------------------------------------------

    def _signing_key(self) -> bytes:
        secret = self._settings.storage_url_signing_key or self._settings.kyc_encryption_key
        if secret is None:
            msg = "File links cannot be signed: set LPG_KYC_ENCRYPTION_KEY."
            raise ServiceUnavailableError(msg)
        return hashlib.sha256(b"lpg-file-url\n" + secret.get_secret_value().encode()).digest()

    def _sign(self, key: str, expires_at: int) -> str:
        message = f"view\n{key}\n{expires_at}".encode()
        return hmac.new(self._signing_key(), message, hashlib.sha256).hexdigest()

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        """A time-limited signed link to the compressed (view) copy.

        The signature is the only credential, so an ``<img>`` tag or a mobile
        image widget can load it without an Authorization header. Absolute so
        the mobile apps can use it directly.
        """
        self._path(key)  # reject malformed keys up front
        expires_at = int(time.time()) + expires_seconds
        query = urlencode({"key": key, "exp": expires_at, "sig": self._sign(key, expires_at)})
        base = (self._settings.storage_public_base_url or self._settings.dashboard_url).rstrip("/")
        return f"{base}{self._settings.api_v1_prefix}/files/view?{query}"

    def verify_signature(self, key: str, expires_at: int, signature: str) -> bool:
        if expires_at < int(time.time()):
            return False
        return hmac.compare_digest(self._sign(key, expires_at), signature)

    # -- visibility ------------------------------------------------------

    def _scan(self) -> DiskUsage:
        self._root.mkdir(parents=True, exist_ok=True)
        stored = count = 0
        for dirpath, _dirs, files in os.walk(self._root):
            for name in files:
                if name.startswith("."):
                    continue
                try:
                    stored += (Path(dirpath) / name).stat().st_size
                    count += 1
                except OSError:
                    continue
        disk = shutil.disk_usage(self._root)
        return DiskUsage(disk.total, disk.free, stored, count)

    async def usage(self) -> DiskUsage:
        """Disk totals plus what uploads occupy (walks the tree: admin use only)."""
        return await asyncio.to_thread(self._scan)

    async def usage_cached(self) -> DiskUsage | None:
        """Cheap free-space reading (no tree walk) for readiness."""
        try:
            disk = await asyncio.to_thread(shutil.disk_usage, self._root)
        except OSError:
            return None
        return DiskUsage(disk.total, disk.free, 0, 0)


def build_file_storage(settings: Settings | None = None) -> LocalDiskFileStorage:
    from lpg.config.settings import get_settings

    return LocalDiskFileStorage(settings or get_settings())


__all__ = ["COMPRESSED_SUFFIX", "DiskUsage", "LocalDiskFileStorage", "build_file_storage"]
