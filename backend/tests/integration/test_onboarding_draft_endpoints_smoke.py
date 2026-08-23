from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def real_lifespan_client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")

    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    get_settings.cache_clear()


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str
) -> tuple[uuid.UUID, uuid.UUID]:
    from sqlalchemy import text

    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Draft Smoke Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"draft-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, :role) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestOnboardingDraftEndpointsThroughRealStack:
    async def test_save_resume_and_discard_draft_lifecycle(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@draft-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. No drafts yet
        empty_list = await real_lifespan_client.get(
            "/api/v1/customers/onboarding-drafts", headers=headers
        )
        assert empty_list.status_code == 200, empty_list.text
        assert empty_list.json()["items"] == []

        # 2. Save a new draft (step 1 only)
        save_response = await real_lifespan_client.post(
            "/api/v1/customers/onboarding-drafts",
            json={
                "current_step": 1,
                "registration_data": {"first_name": "Ramesh", "phone_number": "+919876543210"},
            },
            headers=headers,
        )
        assert save_response.status_code == 201, save_response.text
        draft = save_response.json()
        draft_id = draft["id"]
        assert draft["registration_data"]["first_name"] == "Ramesh"
        assert draft["current_step"] == 1

        # 3. Update the same draft (now at step 3, with KYC data + a blob ref)
        update_response = await real_lifespan_client.post(
            "/api/v1/customers/onboarding-drafts",
            json={
                "draft_id": draft_id,
                "current_step": 3,
                "registration_data": {"first_name": "Ramesh", "phone_number": "+919876543210"},
                "kyc_data": {"doc_type": "aadhaar", "document_number": "123412341234"},
                "kyc_document_blob_ref": "tenant/x/kyc-staging/abc_doc.jpg",
            },
            headers=headers,
        )
        assert update_response.status_code == 201, update_response.text
        updated = update_response.json()
        assert updated["id"] == draft_id
        assert updated["current_step"] == 3
        assert updated["kyc_data"]["doc_type"] == "aadhaar"

        # 4. It shows up in "my drafts"
        list_response = await real_lifespan_client.get(
            "/api/v1/customers/onboarding-drafts", headers=headers
        )
        assert list_response.status_code == 200, list_response.text
        assert len(list_response.json()["items"]) == 1
        assert list_response.json()["items"][0]["id"] == draft_id

        # 5. Fetch it directly (resume)
        get_response = await real_lifespan_client.get(
            f"/api/v1/customers/onboarding-drafts/{draft_id}", headers=headers
        )
        assert get_response.status_code == 200, get_response.text
        assert get_response.json()["current_step"] == 3

        # 6. Discard it
        delete_response = await real_lifespan_client.delete(
            f"/api/v1/customers/onboarding-drafts/{draft_id}", headers=headers
        )
        assert delete_response.status_code == 204, delete_response.text

        # 7. It's gone
        gone_response = await real_lifespan_client.get(
            f"/api/v1/customers/onboarding-drafts/{draft_id}", headers=headers
        )
        assert gone_response.status_code == 404, gone_response.text

    async def test_another_users_draft_is_not_visible(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        password = "correct horse battery staple 42"

        owner_email = f"{uuid.uuid4().hex}@draft-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=owner_email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        owner_token = await _login(real_lifespan_client, email=owner_email, password=password)
        save_response = await real_lifespan_client.post(
            "/api/v1/customers/onboarding-drafts",
            json={"current_step": 1, "registration_data": {"first_name": "Owner Only"}},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert save_response.status_code == 201, save_response.text
        draft_id = save_response.json()["id"]

        other_email = f"{uuid.uuid4().hex}@draft-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=other_email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        other_token = await _login(real_lifespan_client, email=other_email, password=password)

        response = await real_lifespan_client.get(
            f"/api/v1/customers/onboarding-drafts/{draft_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 404, response.text

    async def test_kyc_attachment_upload_returns_blob_ref(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@draft-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/customers/kyc-attachments",
            headers=headers,
            files={"file": ("aadhaar.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert response.status_code == 201, response.text
        blob_ref = response.json()["blob_ref"]
        assert "kyc-staging" in blob_ref
        assert blob_ref.endswith("_aadhaar.jpg")

    async def test_recognize_kyc_document_extracts_fields_from_a_real_image(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """Exercises the real backend OCR "second pass" end to end: upload
        a synthetic-but-real document image, then have the server actually
        run RapidOCR against it (first invocation in a test run downloads
        and caches the ~130MB model set, so this is slow the first time).
        """
        import io

        from PIL import Image, ImageDraw, ImageFont

        email = f"{uuid.uuid4().hex}@draft-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # PIL's default bitmap font is too small/low-quality for OCR to read
        # reliably — use a real scalable font, same as manual verification.
        try:
            font = ImageFont.truetype("arial.ttf", 28)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = font_small = ImageFont.load_default()

        img = Image.new("RGB", (600, 260), "white")
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), "Government of India", fill="black", font=font_small)
        draw.text((30, 80), "SUNITA VERMA", fill="black", font=font)
        draw.text((30, 130), "DOB: 30/05/1995", fill="black", font=font_small)
        draw.text((30, 170), "FEMALE", fill="black", font=font_small)
        draw.text((30, 210), "1234 5678 9012", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        upload_response = await real_lifespan_client.post(
            "/api/v1/customers/kyc-attachments",
            headers=headers,
            files={"file": ("aadhaar.png", buf.getvalue(), "image/png")},
        )
        assert upload_response.status_code == 201, upload_response.text
        blob_ref = upload_response.json()["blob_ref"]

        recognize_response = await real_lifespan_client.post(
            "/api/v1/customers/kyc-attachments/recognize",
            headers=headers,
            json={"blob_ref": blob_ref},
            timeout=180.0,
        )
        assert recognize_response.status_code == 200, recognize_response.text
        body = recognize_response.json()
        assert body["doc_type"] == "aadhaar"
        assert body["document_number"] == "123456789012"
        assert body["full_name"] == "SUNITA VERMA"
        assert body["date_of_birth"] == "1995-05-30"
        assert body["confidence"] > 0.5
