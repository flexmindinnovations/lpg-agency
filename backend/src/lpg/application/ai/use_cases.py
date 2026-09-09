"""`AskAiAssistantUseCase` (ADR-045) — the AI Command Center's orchestrator.

Ties together the kill switch, the budget ceiling, per-tool permission
filtering, the model gateway, and the append-only run ledger. Every check
that can short-circuit before ever touching the gateway does — a disabled
tenant or an over-budget one costs nothing beyond a couple of local reads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from lpg.application.ai.ports import AssistantRun
from lpg.application.ai.tools import TOOL_REGISTRY
from lpg.application.common.cqrs import Query
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.ai.ports import AssistantRunRepository, ModelGatewayPort
    from lpg.application.ai.tools import ToolContext
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.identity.authorize import PermissionChecker
    from lpg.application.identity.ports import AuthenticatedPrincipal
    from lpg.application.tenant.ports import TenantConfigurationRepository

#: Falls back to this when a tenant has never set the `ai_daily_token_budget`
#: `TenantConfiguration` override — mirrors `DEFAULT_WEIGHMENT_TOLERANCE_
#: GRAMS`'s "constant + optional per-tenant override" shape.
DEFAULT_AI_DAILY_TOKEN_BUDGET = 100_000

DisabledReason = Literal["gateway_disabled", "budget_exceeded", "provider_error"]

_SYSTEM_PROMPT = (
    "You are the LPG Agency AI Command Center, an operations assistant for "
    "distributor staff. Answer questions about today's orders, inventory, "
    "and complaints using only the tools available to you -- never guess a "
    "number you could look up. If a question needs data no available tool "
    "can provide, say so plainly rather than inventing an answer. Keep "
    "answers concise and concrete. Your reply is rendered as formatted "
    "markdown, so use it purposefully: a heading or **bold** label for "
    "structure, a bullet or numbered list for enumerations, and a markdown "
    "table when comparing multiple records or metrics side by side. Prefer "
    "short paragraphs and plain sentences when a single fact or a brief "
    "explanation is all that's needed -- do not force structure where "
    "none is warranted."
)


def _is_truthy_config_value(value: object) -> bool:
    """`TenantConfiguration.config_value` is `jsonb` and the generic Set
    Value admin form (no dedicated toggle UI for this key) sends whatever
    string the operator typed, not a JSON boolean — so a stored value of
    `"false"` is a real, live possibility, not a hypothetical. Plain
    `bool(value)` is wrong here: `bool("false")` is `True` in Python, since
    it only checks for a non-empty string. Confirmed live: setting this key
    to the literal text "false" through the real admin UI and asking a
    question came back answered, not disabled, before this helper existed.
    """
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no")
    return bool(value)


@dataclass(frozen=True, slots=True)
class AskAiAssistantQuery(Query):
    question: str


@dataclass(frozen=True, slots=True)
class AskAiAssistantResult:
    answer: str | None
    tools_used: tuple[str, ...]
    disabled_reason: DisabledReason | None


class AskAiAssistantUseCase:
    def __init__(
        self,
        *,
        gateway: ModelGatewayPort,
        tenant_config_repository: TenantConfigurationRepository,
        assistant_run_repository: AssistantRunRepository,
        permission_checker: PermissionChecker,
        tool_context: ToolContext,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._gateway = gateway
        self._tenant_config_repository = tenant_config_repository
        self._assistant_run_repository = assistant_run_repository
        self._permission_checker = permission_checker
        self._tool_context = tool_context
        self._unit_of_work = unit_of_work

    async def _gateway_enabled(self, tenant_id: uuid.UUID) -> bool:
        config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=tenant_id, config_key="ai_gateway_enabled"
            )
        )
        return _is_truthy_config_value(config.config_value) if config is not None else False

    async def _effective_daily_budget(self, tenant_id: uuid.UUID) -> int:
        config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=tenant_id, config_key="ai_daily_token_budget"
            )
        )
        return int(config.config_value) if config is not None else DEFAULT_AI_DAILY_TOKEN_BUDGET

    async def execute(
        self, query: AskAiAssistantQuery, *, principal: AuthenticatedPrincipal
    ) -> AskAiAssistantResult:
        if not await self._gateway_enabled(principal.tenant_id):
            return AskAiAssistantResult(
                answer=None, tools_used=(), disabled_reason="gateway_disabled"
            )

        budget = await self._effective_daily_budget(principal.tenant_id)
        used_today = await self._assistant_run_repository.get_todays_token_usage()
        if used_today >= budget:
            await self._record_run(
                principal=principal,
                question=query.question,
                status="budget_exceeded",
                tools_used=(),
                provider="",
                model="",
                prompt_tokens=0,
                completion_tokens=0,
                tool_turns=0,
                latency_ms=None,
                error_message=None,
            )
            return AskAiAssistantResult(
                answer=None, tools_used=(), disabled_reason="budget_exceeded"
            )

        available_tools = [
            tool
            for tool in TOOL_REGISTRY
            if self._permission_checker.has_permission(principal, tool.required_permission)
        ]
        handlers_by_name = {tool.declaration.name: tool.handler for tool in available_tools}

        async def tool_executor(name: str, _arguments: dict[str, object]) -> dict[str, object]:
            handler = handlers_by_name.get(name)
            if handler is None:
                # A hallucinated call, or one to a tool this principal isn't
                # granted — rejected here, never executed. The real defense
                # against prompt injection is this backend gate, not the
                # system prompt's wording (per the user's own architecture
                # doc).
                return {"error": f"Tool '{name}' is not available."}
            return await handler(principal, self._tool_context)

        started = time.monotonic()
        result = await self._gateway.run_with_tools(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=query.question,
            tools=tuple(tool.declaration for tool in available_tools),
            tool_executor=tool_executor,
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        if result is None:
            await self._record_run(
                principal=principal,
                question=query.question,
                status="provider_error",
                tools_used=(),
                provider="",
                model="",
                prompt_tokens=0,
                completion_tokens=0,
                tool_turns=0,
                latency_ms=latency_ms,
                error_message="The model gateway returned no result.",
            )
            return AskAiAssistantResult(
                answer=None, tools_used=(), disabled_reason="provider_error"
            )

        await self._record_run(
            principal=principal,
            question=query.question,
            status="success",
            tools_used=result.tools_used,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            tool_turns=result.tool_turns,
            latency_ms=latency_ms,
            error_message=None,
        )
        return AskAiAssistantResult(
            answer=result.final_answer, tools_used=result.tools_used, disabled_reason=None
        )

    async def _record_run(
        self,
        *,
        principal: AuthenticatedPrincipal,
        question: str,
        status: str,
        tools_used: tuple[str, ...],
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        tool_turns: int,
        latency_ms: int | None,
        error_message: str | None,
    ) -> None:
        run = AssistantRun(
            id=self._assistant_run_repository.next_id(),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            role=principal.role,
            question=question,
            tools_used=list(tools_used),
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tool_turns=tool_turns,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            correlation_id=None,
            created_at=datetime.now(UTC),
        )
        await self._assistant_run_repository.add(run)
        await self._unit_of_work.commit()
