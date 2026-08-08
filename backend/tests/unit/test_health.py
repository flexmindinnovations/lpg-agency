"""Health and readiness endpoint behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestLiveness:
    async def test_returns_200_without_any_dependency(self, client: AsyncClient) -> None:
        """Liveness must not consult PostgreSQL or Redis.

        This is the whole point of the split. If liveness checked the database,
        a brief database blip would restart every instance at once — turning a
        recoverable wobble into an outage.
        """
        response = await client.get("/health/live")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "alive"
        assert body["app_name"]
        assert body["version"]

    async def test_echoes_correlation_id(self, client: AsyncClient) -> None:
        supplied = "test-correlation-id-1234"

        response = await client.get("/health/live", headers={"X-Correlation-ID": supplied})

        assert response.headers["X-Correlation-ID"] == supplied

    async def test_generates_correlation_id_when_absent(self, client: AsyncClient) -> None:
        response = await client.get("/health/live")

        generated = response.headers.get("X-Correlation-ID")
        assert generated
        assert len(generated) >= 32  # a UUID4


class TestReadiness:
    async def test_reports_not_ready_when_dependencies_unavailable(
        self, client: AsyncClient
    ) -> None:
        """Without the lifespan, no connections exist, so readiness must fail.

        A readiness endpoint that returns ready when it has checked nothing is
        worse than no readiness endpoint — it actively asserts a false claim to
        the load balancer.
        """
        response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
