from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.customer import get_onboarding_draft_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.onboarding_draft import (
    OnboardingDraftListResponse,
    OnboardingDraftResponse,
    SaveOnboardingDraftRequest,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import OnboardingDraftRepository
from lpg.application.customer.use_cases import (
    DeleteOnboardingDraftCommand,
    DeleteOnboardingDraftUseCase,
    GetOnboardingDraftQuery,
    GetOnboardingDraftUseCase,
    ListMyOnboardingDraftsQuery,
    ListMyOnboardingDraftsUseCase,
    SaveOnboardingDraftCommand,
    SaveOnboardingDraftUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/customers/onboarding-drafts", tags=["Customer Onboarding Drafts"])


@router.post(
    "",
    response_model=OnboardingDraftResponse,
    status_code=201,
    dependencies=[Depends(require_permission("onboarding_drafts:manage"))],
)
async def save_onboarding_draft(
    request: SaveOnboardingDraftRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[OnboardingDraftRepository, Depends(get_onboarding_draft_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnboardingDraftResponse:
    """Create-or-update, keyed by `request.draft_id` — omit it to create a
    new draft, pass an existing id to overwrite that draft's snapshot.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = SaveOnboardingDraftUseCase(repository, unit_of_work)
    draft = await use_case.execute(
        SaveOnboardingDraftCommand(
            tenant_id=principal.tenant_id,
            created_by=principal.user_id,
            draft_id=request.draft_id,
            branch_id=request.branch_id,
            current_step=request.current_step,
            registration_data=request.registration_data,
            address_data=request.address_data,
            kyc_data=request.kyc_data,
            kyc_document_blob_ref=request.kyc_document_blob_ref,
        )
    )
    return OnboardingDraftResponse.model_validate(draft)


@router.get(
    "",
    response_model=OnboardingDraftListResponse,
    dependencies=[Depends(require_permission("onboarding_drafts:manage"))],
)
async def list_my_onboarding_drafts(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[OnboardingDraftRepository, Depends(get_onboarding_draft_repository)],
) -> OnboardingDraftListResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = ListMyOnboardingDraftsUseCase(repository)
    drafts = await use_case.execute(
        ListMyOnboardingDraftsQuery(tenant_id=principal.tenant_id, created_by=principal.user_id)
    )
    return OnboardingDraftListResponse(
        items=[OnboardingDraftResponse.model_validate(d) for d in drafts]
    )


@router.get(
    "/{draft_id}",
    response_model=OnboardingDraftResponse,
    dependencies=[Depends(require_permission("onboarding_drafts:manage"))],
)
async def get_onboarding_draft(
    draft_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[OnboardingDraftRepository, Depends(get_onboarding_draft_repository)],
) -> OnboardingDraftResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = GetOnboardingDraftUseCase(repository)
    draft = await use_case.execute(
        GetOnboardingDraftQuery(
            draft_id=draft_id, tenant_id=principal.tenant_id, requested_by=principal.user_id
        )
    )
    if draft is None:
        msg = f"No draft visible with id {draft_id}."
        raise NotFoundError(msg, draft_id=str(draft_id))
    return OnboardingDraftResponse.model_validate(draft)


@router.delete(
    "/{draft_id}",
    status_code=204,
    dependencies=[Depends(require_permission("onboarding_drafts:manage"))],
)
async def delete_onboarding_draft(
    draft_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[OnboardingDraftRepository, Depends(get_onboarding_draft_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = DeleteOnboardingDraftUseCase(repository, unit_of_work)
    await use_case.execute(
        DeleteOnboardingDraftCommand(
            draft_id=draft_id, tenant_id=principal.tenant_id, requested_by=principal.user_id
        )
    )
