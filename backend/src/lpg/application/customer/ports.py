from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from lpg.domain.customer.customer import Customer
    from lpg.domain.customer.onboarding_draft import OnboardingDraftEntry


class FieldEncryptor(Protocol):
    """Application-layer field encryption at rest.

    Owned by the repository, never the domain: `Customer`/`KycDocument`
    always hold plaintext in memory — encryption is purely a persistence
    concern, the same "persistence shape vs domain shape" separation
    `models/tenant.py`'s module docstring documents generally.
    """

    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


class CustomerRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, customer: Customer) -> None: ...

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None: ...

    async def get_by_phone(self, phone_number: str) -> Customer | None: ...

    async def get_by_consumer_number(self, consumer_number: str) -> Customer | None: ...

    async def get_by_lpg_subsidy_id(self, lpg_subsidy_id: str) -> Customer | None: ...

    async def get_by_identity_user_id(self, identity_user_id: uuid.UUID) -> Customer | None: ...

    async def list_customers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> list[Customer]: ...

    async def count_customers(self, search: str | None = None) -> int: ...


class ConsumerNumberSequence(Protocol):
    """A per-tenant counter suggesting the next Consumer Number.

    Advisory only — `consumer_number` uniqueness is enforced independently
    (DB unique constraint + app-layer pre-check), so a caller is always free
    to submit a different, manually-entered value instead (e.g. a legacy
    number being migrated in). Gaps in the sequence are expected and benign,
    the same as any database sequence — a `next()` call that's peeked but
    never used (dialog opened then cancelled) simply isn't suggested again.
    """

    async def next(self) -> str: ...


@dataclass(frozen=True, slots=True)
class DocumentOcrResult:
    text: str
    confidence: float  # 0-1


class DocumentOcrPort(Protocol):
    """Server-side OCR for the KYC auto-fill "second pass" (D-onboarding).

    The browser already runs a fast, in-page OCR pass for instant feedback
    (`document-ocr.service.ts`, same regex-based field parsing). This port
    is the slower, more-accurate follow-up that refines the pre-filled
    fields once it completes — the image is already uploaded to and stored
    by our own backend for the KYC record regardless (see
    `FileStorage`/`kyc-attachments`), so running OCR on it here server-side
    adds no new privacy exposure, just better accuracy from a heavier model
    than is practical to ship to every browser.
    """

    async def recognize(self, image_bytes: bytes) -> DocumentOcrResult: ...


class OnboardingDraftRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, draft: OnboardingDraftEntry) -> OnboardingDraftEntry: ...

    async def get_by_id(
        self, draft_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> OnboardingDraftEntry | None: ...

    async def list_by_user(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID
    ) -> list[OnboardingDraftEntry]: ...

    async def delete(self, draft_id: uuid.UUID, tenant_id: uuid.UUID) -> None: ...
