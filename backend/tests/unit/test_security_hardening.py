"""Security hardening: OTP attempt cap, tenant-scoped storage, upload rules."""
# ruff: noqa: ARG002

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from lpg.api.v1.uploads import read_upload, safe_filename
from lpg.application.common.errors import NotFoundError, RateLimitExceededError, ValidationError
from lpg.infrastructure.identity.otp_service import MAX_VERIFY_ATTEMPTS, OtpService
from lpg.infrastructure.storage.scoped import TenantScopedFileStorage


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.data.pop(key, None)

    async def incr(self, key: str) -> int:
        self.data[key] = str(int(self.data.get(key, "0")) + 1)
        return int(self.data[key])

    async def ttl(self, key: str) -> int:
        return 300

    async def expire(self, key: str, seconds: int) -> None: ...


def _otp_service() -> OtpService:
    client = SimpleNamespace(client=FakeRedis())
    settings = SimpleNamespace(otp_length=6, otp_ttl_seconds=300)
    return OtpService(client, settings)  # type: ignore[arg-type]


async def test_otp_is_destroyed_after_too_many_wrong_codes() -> None:
    service = _otp_service()
    code = await service.issue("k")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(MAX_VERIFY_ATTEMPTS - 1):
        assert await service.verify("k", wrong) is False
    with pytest.raises(RateLimitExceededError):
        await service.verify("k", wrong)
    # The right code no longer works: a new one must be requested.
    from lpg.application.common.errors import OtpExpiredError

    with pytest.raises(OtpExpiredError):
        await service.verify("k", code)


async def test_correct_otp_still_works_after_some_misses() -> None:
    service = _otp_service()
    code = await service.issue("k")
    assert await service.verify("k", "x" * 6) is False
    assert await service.verify("k", code) is True


class FakeStorage:
    async def upload(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...
    async def download(self, key: str) -> bytes | None:
        return b"x"

    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool:
        return True

    async def url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return f"https://signed/{key}"


async def test_scoped_storage_blocks_other_tenants_and_traversal() -> None:
    tenant, other = uuid.uuid4(), uuid.uuid4()
    storage = TenantScopedFileStorage(FakeStorage(), tenant)
    assert await storage.download(f"tenant/{tenant}/kyc/a.png") == b"x"
    for bad in (f"tenant/{other}/kyc/a.png", f"tenant/{tenant}/../{other}/a.png", "kyc/a.png"):
        with pytest.raises(NotFoundError):
            await storage.download(bad)
        with pytest.raises(NotFoundError):
            await storage.url(bad)


def test_safe_filename_strips_paths_and_odd_characters() -> None:
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("a b<script>.png") == "a_b_script_.png"
    assert safe_filename(None) == "file"
    assert safe_filename("...") == "file"


class FakeUpload:
    def __init__(self, data: bytes, content_type: str, filename: str = "a.png") -> None:
        self._data = data
        self.content_type = content_type
        self.filename = filename

    async def read(self, size: int = -1) -> bytes:
        return self._data if size < 0 else self._data[:size]


async def test_upload_rules() -> None:
    data, name, ctype = await read_upload(FakeUpload(b"abc", "image/png"))  # type: ignore[arg-type]
    assert (data, name, ctype) == (b"abc", "a.png", "image/png")
    with pytest.raises(ValidationError):
        await read_upload(FakeUpload(b"<html>", "text/html"))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await read_upload(FakeUpload(b"x" * (10 * 1024 * 1024 + 1), "image/png"))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await read_upload(FakeUpload(b"", "image/png"))  # type: ignore[arg-type]
