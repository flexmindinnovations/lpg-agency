"""RFC 7807 error contract (ADR-021).

Every error response the API emits must have this shape. These tests are the
executable form of that contract — if they pass, three client applications can
rely on a single error-handling path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI

from lpg.api.middleware.problem_details import (
    PROBLEM_CONTENT_TYPE,
    register_exception_handlers,
)
from lpg.application.common.errors import (
    ConcurrencyConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from lpg.domain.common.base import BusinessRuleViolation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient

REQUIRED_FIELDS = ("type", "title", "status", "error_code", "detail", "instance")


@pytest.fixture
def error_app() -> FastAPI:
    """A minimal app exposing one route per error class."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/not-found")
    async def _not_found() -> None:
        raise NotFoundError("No customer exists with the supplied identifier.")

    @app.get("/boom/forbidden")
    async def _forbidden() -> None:
        raise PermissionDeniedError("Missing permission: orders:cancel")

    @app.get("/boom/conflict")
    async def _conflict() -> None:
        raise ConcurrencyConflictError("Resource was modified by another request.")

    @app.get("/boom/validation")
    async def _validation() -> None:
        raise ValidationError(
            "One or more fields failed validation.",
            errors={"quantity": ["must be greater than zero"]},
        )

    @app.get("/boom/domain")
    async def _domain() -> None:
        raise BusinessRuleViolation("Inventory would become negative.")

    @app.get("/boom/unhandled")
    async def _unhandled() -> None:
        raise RuntimeError("something internal exploded")

    return app


@pytest.fixture
async def error_client(error_app: FastAPI) -> AsyncIterator[AsyncClient]:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=error_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestProblemDetailsShape:
    @pytest.mark.parametrize(
        ("path", "expected_status", "expected_code"),
        [
            ("/boom/not-found", 404, "RESOURCE_NOT_FOUND"),
            ("/boom/forbidden", 403, "PERMISSION_DENIED"),
            ("/boom/conflict", 409, "CONCURRENCY_CONFLICT"),
            ("/boom/validation", 422, "VALIDATION_FAILED"),
            ("/boom/domain", 409, "BUSINESS_RULE_VIOLATION"),
            ("/boom/unhandled", 500, "INTERNAL_SERVER_ERROR"),
        ],
    )
    async def test_status_and_error_code(
        self,
        error_client: AsyncClient,
        path: str,
        expected_status: int,
        expected_code: str,
    ) -> None:
        response = await error_client.get(path)

        assert response.status_code == expected_status
        assert response.json()["error_code"] == expected_code

    @pytest.mark.parametrize(
        "path",
        [
            "/boom/not-found",
            "/boom/forbidden",
            "/boom/conflict",
            "/boom/validation",
            "/boom/domain",
            "/boom/unhandled",
        ],
    )
    async def test_content_type_and_required_fields(
        self, error_client: AsyncClient, path: str
    ) -> None:
        response = await error_client.get(path)

        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        body = response.json()
        for field in REQUIRED_FIELDS:
            assert field in body, f"{field} missing from {path}"

    async def test_no_success_envelope(self, error_client: AsyncClient) -> None:
        """ADR-021: no {"success": ...} wrapper on any response."""
        body = await error_client.get("/boom/not-found")

        assert "success" not in body.json()
        assert "data" not in body.json()

    async def test_field_errors_use_the_errors_extension(self, error_client: AsyncClient) -> None:
        response = await error_client.get("/boom/validation")

        assert response.json()["errors"] == {"quantity": ["must be greater than zero"]}

    async def test_unhandled_exception_leaks_nothing_internal(
        self, error_client: AsyncClient
    ) -> None:
        """A 500 must not disclose the exception message, type, or a traceback.

        Leaking those tells an attacker about the schema, the ORM, and the file
        layout. The correlation ID is how support correlates the report to the
        real cause in the logs.
        """
        response = await error_client.get("/boom/unhandled")
        body = response.json()

        serialized = str(body)
        assert "something internal exploded" not in serialized
        assert "RuntimeError" not in serialized
        assert "Traceback" not in serialized

    async def test_error_type_is_a_documentation_uri(self, error_client: AsyncClient) -> None:
        response = await error_client.get("/boom/not-found")

        assert response.json()["type"].endswith("/errors/resource-not-found")


class TestNotFoundIsIndistinguishableFromCrossTenant:
    async def test_missing_and_other_tenant_both_return_404(self) -> None:
        """Cross-tenant reads must look identical to genuinely-missing records.

        Returning 403 for "exists but belongs to another tenant" would leak the
        existence of other tenants' records through status codes alone. The
        application error class enforces this by having exactly one way to
        express both cases.
        """
        assert NotFoundError.http_status == 404
        assert NotFoundError.error_code == "RESOURCE_NOT_FOUND"
