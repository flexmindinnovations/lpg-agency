from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

# `DocumentOcrPort` / `DocumentOcrResult` moved to `application.common.ports`
# when driver/vehicle compliance started sharing the OCR engine. Re-exported
# here (explicit `as` so it counts as a public re-export under mypy --strict)
# so existing `from lpg.application.customer.ports import ...` imports keep
# working.
from lpg.application.common.ports import DocumentOcrPort as DocumentOcrPort
from lpg.application.common.ports import DocumentOcrResult as DocumentOcrResult

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
