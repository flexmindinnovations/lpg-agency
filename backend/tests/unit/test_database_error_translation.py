"""DA-03: a database driver error never reaches the client verbatim.

Before this, the Unit of Work dependency turned any unexpected exception into
`HTTPException(500, detail=str(e))`, so a constraint violation sent the SQL
text, schema/table names, the tenant id and every bound parameter to the
browser. These tests wire the handlers exactly as `lpg.api.app.create_app`
does and raise real SQLAlchemy `DBAPIError`s carrying a PostgreSQL SQLSTATE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from lpg.api.middleware.problem_details import PROBLEM_CONTENT_TYPE, register_exception_handlers
from lpg.infrastructure.persistence.errors import (
    DATABASE_ERROR_TYPES,
    sqlstate_of,
    translate_database_error,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_TENANT = "1875f5e3-0000-4000-8000-000000000001"
_SQL = "INSERT INTO inventory.goods_receipt_note (id, tenant_id, number) VALUES ($1, $2, $3)"


class _DriverError(Exception):
    """Stands in for an asyncpg exception: it exposes `sqlstate`."""

    def __init__(self, sqlstate: str, message: str) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def _integrity(sqlstate: str) -> IntegrityError:
    orig = _DriverError(sqlstate, 'violates constraint "ck_goods_receipt_note_source"')
    return IntegrityError(_SQL, (_TENANT, "GRN000001"), orig)


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(
        app,
        database_error_types=DATABASE_ERROR_TYPES,
        translate_database_error=translate_database_error,
    )

    @app.get("/unique")
    async def _unique() -> None:
        raise _integrity("23505")

    @app.get("/check")
    async def _check() -> None:
        raise _integrity("23514")

    @app.get("/too-long")
    async def _too_long() -> None:
        raise DataError(_SQL, (_TENANT,), _DriverError("22001", "value too long"))

    @app.get("/unknown")
    async def _unknown() -> None:
        raise OperationalError(_SQL, (_TENANT,), _DriverError("57P01", "admin shutdown"))

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def _assert_nothing_internal(body_text: str) -> None:
    for leak in ("INSERT", "inventory.", "goods_receipt_note", _TENANT, "GRN000001", "ck_"):
        assert leak not in body_text


async def test_a_unique_violation_is_a_plain_409(client: AsyncClient) -> None:
    response = await client.get("/unique")
    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["error_code"] == "DUPLICATE_RECORD"
    assert "already exists" in response.json()["detail"]
    _assert_nothing_internal(response.text)


async def test_a_check_violation_is_a_plain_422(client: AsyncClient) -> None:
    response = await client.get("/check")
    assert response.status_code == 422
    assert response.json()["error_code"] == "INVALID_VALUE"
    _assert_nothing_internal(response.text)


async def test_a_too_long_value_is_a_plain_422(client: AsyncClient) -> None:
    response = await client.get("/too-long")
    assert response.status_code == 422
    assert "too long" in response.json()["detail"]
    _assert_nothing_internal(response.text)


async def test_an_unknown_database_error_is_a_generic_500(client: AsyncClient) -> None:
    response = await client.get("/unknown")
    assert response.status_code == 500
    assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"
    _assert_nothing_internal(response.text)


def test_sqlstate_is_read_from_the_wrapped_driver_error() -> None:
    assert sqlstate_of(_integrity("23505")) == "23505"
    assert translate_database_error(ValueError("not a database error")) is None
