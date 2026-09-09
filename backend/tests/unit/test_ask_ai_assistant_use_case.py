"""Unit tests for `AskAiAssistantUseCase` (ADR-045) — mocked gateway/
repositories, no database, no real Gemini calls."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from lpg.application.ai.ports import AgentRunResult, ToolExecutor
from lpg.application.ai.tools import ToolContext
from lpg.application.ai.use_cases import (
    DEFAULT_AI_DAILY_TOKEN_BUDGET,
    AskAiAssistantQuery,
    AskAiAssistantUseCase,
)


def _principal(*, permission_codes: frozenset[str] = frozenset()) -> MagicMock:
    principal = MagicMock()
    principal.tenant_id = uuid.uuid4()
    principal.user_id = uuid.uuid4()
    principal.role = "manager"
    principal.permission_codes = permission_codes
    return principal


def _tenant_config_repository(*, gateway_enabled: object, budget: int | None = None) -> MagicMock:
    """A tiny fake `TenantConfigurationRepository` — `list_for_tenant_and_key`
    returning zero or one already-resolved entry is enough for
    `TenantConfigurationResolver.resolve` to answer correctly, matching how
    `GetEffectiveTenantConfigurationUseCase` is exercised elsewhere in this
    codebase's own tests."""
    from lpg.domain.tenant.tenant_configuration import TenantConfiguration

    repository = MagicMock()

    async def list_for_tenant_and_key(tenant_id: uuid.UUID, config_key: str) -> list[object]:
        from datetime import UTC, datetime

        if config_key == "ai_gateway_enabled":
            return [
                TenantConfiguration(
                    uuid.uuid4(), tenant_id, config_key, gateway_enabled, datetime.now(UTC)
                )
            ]
        if config_key == "ai_daily_token_budget" and budget is not None:
            return [
                TenantConfiguration(
                    uuid.uuid4(), tenant_id, config_key, budget, datetime.now(UTC)
                )
            ]
        return []

    repository.list_for_tenant_and_key = AsyncMock(side_effect=list_for_tenant_and_key)
    return repository


def _tool_context() -> ToolContext:
    order_repository = MagicMock()
    order_repository.count_orders = AsyncMock(return_value=0)
    inventory_repository = MagicMock()
    inventory_repository.get_balance_summary = AsyncMock(return_value={})
    complaint_uow = MagicMock()
    complaint_uow.__aenter__ = AsyncMock(return_value=complaint_uow)
    complaint_uow.__aexit__ = AsyncMock(return_value=None)
    complaint_uow.complaints.count_complaints = AsyncMock(return_value=0)
    return ToolContext(
        order_repository=order_repository,
        inventory_repository=inventory_repository,
        complaint_uow=complaint_uow,
    )


def _unit_of_work() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    return uow


async def test_kill_switch_off_short_circuits_before_touching_the_gateway() -> None:
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock()
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=False),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    result = await use_case.execute(
        AskAiAssistantQuery(question="What's today's inventory?"), principal=_principal()
    )

    assert result.answer is None
    assert result.disabled_reason == "gateway_disabled"
    gateway.run_with_tools.assert_not_awaited()
    assistant_run_repository.add.assert_not_awaited()


async def test_kill_switch_off_as_the_literal_string_false_is_still_off() -> None:
    """Regression test — live-verified via the real admin UI: the generic
    Tenant Configuration 'Set Value' form has no dedicated toggle for this
    key, so it persists whatever string the operator typed
    (`config_value = "false"`, not the JSON boolean `false`). A naive
    `bool(config_value)` reads that as truthy (`bool("false") is True` in
    Python) and answers anyway -- this is exactly the bug caught live: the
    key was set to "false" through the real UI and the assistant answered
    a question instead of declining."""
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock()
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled="false"),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    result = await use_case.execute(
        AskAiAssistantQuery(question="What's today's inventory?"), principal=_principal()
    )

    assert result.disabled_reason == "gateway_disabled"
    gateway.run_with_tools.assert_not_awaited()


async def test_budget_exceeded_short_circuits_before_touching_the_gateway() -> None:
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock()
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    assistant_run_repository.get_todays_token_usage = AsyncMock(
        return_value=DEFAULT_AI_DAILY_TOKEN_BUDGET
    )
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=True),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    result = await use_case.execute(
        AskAiAssistantQuery(question="What's today's inventory?"), principal=_principal()
    )

    assert result.disabled_reason == "budget_exceeded"
    gateway.run_with_tools.assert_not_awaited()
    # Still recorded, for observability of the throttling itself.
    assistant_run_repository.add.assert_awaited_once()


async def test_happy_path_records_the_run_and_returns_the_answer() -> None:
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock(
        return_value=AgentRunResult(
            final_answer="You have 1200 filled cylinders.",
            tools_used=("get_inventory_overview",),
            prompt_tokens=50,
            completion_tokens=20,
            tool_turns=1,
            provider="gemini",
            model="gemini-2.0-flash",
        )
    )
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    assistant_run_repository.get_todays_token_usage = AsyncMock(return_value=0)
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=True),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    result = await use_case.execute(
        AskAiAssistantQuery(question="What's today's inventory?"), principal=_principal()
    )

    assert result.answer == "You have 1200 filled cylinders."
    assert result.tools_used == ("get_inventory_overview",)
    assert result.disabled_reason is None
    assistant_run_repository.add.assert_awaited_once()
    recorded_run = assistant_run_repository.add.await_args.args[0]
    assert recorded_run.status == "success"
    assert recorded_run.prompt_tokens == 50


async def test_a_tool_a_principal_lacks_permission_for_is_never_offered_to_the_gateway() -> None:
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock(
        return_value=AgentRunResult(
            final_answer="I don't have access to that information.",
            tools_used=(),
            prompt_tokens=10,
            completion_tokens=5,
            tool_turns=0,
            provider="gemini",
            model="gemini-2.0-flash",
        )
    )
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    assistant_run_repository.get_todays_token_usage = AsyncMock(return_value=0)
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=False)  # holds nothing

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=True),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    await use_case.execute(
        AskAiAssistantQuery(question="Anything?"), principal=_principal()
    )

    call = gateway.run_with_tools.await_args
    assert call.kwargs["tools"] == ()


async def test_a_hallucinated_tool_call_is_rejected_not_executed() -> None:
    """The tool_executor closure passed to the gateway must reject a tool
    name the gateway didn't actually declare/offer — the real
    prompt-injection defense."""
    captured_executor: dict[str, ToolExecutor] = {}

    async def fake_run_with_tools(**kwargs: object) -> AgentRunResult:
        captured_executor["executor"] = kwargs["tool_executor"]  # type: ignore[assignment]
        return AgentRunResult(
            final_answer="ok",
            tools_used=(),
            prompt_tokens=1,
            completion_tokens=1,
            tool_turns=0,
            provider="gemini",
            model="gemini-2.0-flash",
        )

    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock(side_effect=fake_run_with_tools)
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    assistant_run_repository.get_todays_token_usage = AsyncMock(return_value=0)
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=True),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    await use_case.execute(AskAiAssistantQuery(question="Anything?"), principal=_principal())

    executor = captured_executor["executor"]
    result = await executor("delete_everything", {})
    assert "error" in result


async def test_gateway_returning_none_is_recorded_as_a_provider_error() -> None:
    gateway = MagicMock()
    gateway.run_with_tools = AsyncMock(return_value=None)
    assistant_run_repository = MagicMock()
    assistant_run_repository.next_id = MagicMock(return_value=uuid.uuid4())
    assistant_run_repository.add = AsyncMock()
    assistant_run_repository.get_todays_token_usage = AsyncMock(return_value=0)
    permission_checker = MagicMock()
    permission_checker.has_permission = MagicMock(return_value=True)

    use_case = AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=_tenant_config_repository(gateway_enabled=True),
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=_tool_context(),
        unit_of_work=_unit_of_work(),
    )

    result = await use_case.execute(
        AskAiAssistantQuery(question="Anything?"), principal=_principal()
    )

    assert result.disabled_reason == "provider_error"
    recorded_run = assistant_run_repository.add.await_args.args[0]
    assert recorded_run.status == "provider_error"
