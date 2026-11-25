"""An unconfigured or unreachable object store is a 503, never a bare 500."""

from __future__ import annotations

import pytest

from lpg.application.common.errors import ServiceUnavailableError
from lpg.config.settings import Settings
from lpg.infrastructure.storage.client import S3CompatibleFileStorage


@pytest.mark.parametrize("endpoint", ["", "http://127.0.0.1:1"])
async def test_upload_without_working_storage_raises_service_unavailable(endpoint: str) -> None:
    settings = Settings(storage_endpoint_url=endpoint, storage_bucket="lpg", storage_region="blr1")
    storage = S3CompatibleFileStorage(settings)

    with pytest.raises(ServiceUnavailableError, match="LPG_STORAGE"):
        await storage.upload("tenant/x/kyc-staging/a.png", b"data", content_type="image/png")
