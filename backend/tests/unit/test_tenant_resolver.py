"""The Phase 2 interim ``TenantResolver`` — no database required."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from lpg.application.common.errors import TenantContextMissingError
from lpg.infrastructure.tenant.header_resolver import (
    TENANT_HEADER,
    USER_HEADER,
    HeaderTenantResolver,
)


def _request(headers: dict[str, str]) -> SimpleNamespace:
    """A minimal duck-typed stand-in for ``starlette.requests.Request``.

    The resolver only ever touches ``request.headers.get(...)``, so a fake
    this narrow is honest about what the contract actually is, and keeps this
    a unit test rather than requiring the full ASGI machinery.
    """
    return SimpleNamespace(headers=headers)


class TestHeaderTenantResolver:
    async def test_resolves_tenant_id_from_header(self) -> None:
        tenant_id = uuid.uuid4()
        resolver = HeaderTenantResolver()

        context = await resolver.resolve(_request({TENANT_HEADER: str(tenant_id)}))

        assert context.tenant_id == tenant_id
        assert context.user_id is None

    async def test_resolves_optional_user_id(self) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        resolver = HeaderTenantResolver()

        context = await resolver.resolve(
            _request({TENANT_HEADER: str(tenant_id), USER_HEADER: str(user_id)})
        )

        assert context.user_id == user_id

    async def test_raises_when_header_missing(self) -> None:
        resolver = HeaderTenantResolver()

        with pytest.raises(TenantContextMissingError):
            await resolver.resolve(_request({}))

    async def test_raises_when_header_is_not_a_uuid(self) -> None:
        resolver = HeaderTenantResolver()

        with pytest.raises(TenantContextMissingError):
            await resolver.resolve(_request({TENANT_HEADER: "not-a-uuid"}))

    async def test_error_maps_to_401_with_a_stable_code(self) -> None:
        resolver = HeaderTenantResolver()

        with pytest.raises(TenantContextMissingError) as exc_info:
            await resolver.resolve(_request({}))

        assert exc_info.value.http_status == 401
        assert exc_info.value.error_code == "TENANT_CONTEXT_MISSING"
