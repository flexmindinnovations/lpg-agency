"""FastAPI router for the AI Command Center (ADR-045).

`POST /ai/ask`, gated by `ai:read` — granted only to `super_admin,
agency_admin, manager`. A `disabled_reason` in the response (kill switch
off, daily budget exceeded, provider error) is a normal, expected outcome
for a caller to render, never an HTTP error status.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.ai import get_ask_ai_assistant_use_case
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.schemas.ai import AskAiAssistantRequest, AskAiAssistantResponse
from lpg.application.ai.use_cases import AskAiAssistantQuery, AskAiAssistantUseCase
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post(
    "/ask",
    response_model=AskAiAssistantResponse,
    summary="Ask the AI Command Center an operational question",
)
async def ask_ai_assistant(
    request: AskAiAssistantRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("ai:read"))],
    use_case: Annotated[AskAiAssistantUseCase, Depends(get_ask_ai_assistant_use_case)],
) -> AskAiAssistantResponse:
    result = await use_case.execute(
        AskAiAssistantQuery(question=request.question), principal=principal
    )
    return AskAiAssistantResponse(
        answer=result.answer,
        tools_used=list(result.tools_used),
        disabled_reason=result.disabled_reason,
    )
