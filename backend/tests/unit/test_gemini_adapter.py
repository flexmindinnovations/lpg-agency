"""Unit tests for `GeminiModelGateway` (ADR-045) — the tool-calling loop and
graceful-degradation behavior, all against a mocked `google.genai.Client`.
No real network call is made anywhere in this file."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lpg.application.ai.ports import ToolDeclaration
from lpg.infrastructure.ai.gemini_adapter import GeminiModelGateway


def _usage(prompt: int = 10, completion: int = 5) -> MagicMock:
    usage = MagicMock()
    usage.prompt_token_count = prompt
    usage.candidates_token_count = completion
    return usage


def _final_response(text: str) -> MagicMock:
    """A response with no function calls — the model is done."""
    response = MagicMock()
    response.usage_metadata = _usage()
    response.function_calls = None
    response.text = text
    return response


def _tool_call_response(*, tool_name: str, args: dict[str, Any]) -> MagicMock:
    """A response requesting exactly one tool call."""
    call = MagicMock()
    call.name = tool_name
    call.args = args

    response = MagicMock()
    response.usage_metadata = _usage()
    response.function_calls = [call]
    candidate = MagicMock()
    candidate.content = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.fixture
def gateway() -> GeminiModelGateway:
    return GeminiModelGateway(api_key="test-key", model="gemini-2.0-flash")


async def test_returns_final_answer_with_no_tool_calls(gateway: GeminiModelGateway) -> None:
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=_final_response("It's sunny."))
    with patch("google.genai.Client", return_value=mock_client):
        result = await gateway.run_with_tools(
            system_prompt="You are helpful.",
            user_prompt="What's the weather?",
            tools=(),
            tool_executor=AsyncMock(),
        )

    assert result is not None
    assert result.final_answer == "It's sunny."
    assert result.tools_used == ()
    assert result.tool_turns == 0
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5


async def test_executes_a_tool_call_and_returns_the_final_answer(
    gateway: GeminiModelGateway,
) -> None:
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[
            _tool_call_response(tool_name="get_inventory_overview", args={}),
            _final_response("You have 1200 filled cylinders."),
        ]
    )
    tool_executor = AsyncMock(return_value={"filled": 1200})

    with patch("google.genai.Client", return_value=mock_client):
        result = await gateway.run_with_tools(
            system_prompt="You are helpful.",
            user_prompt="What's today's inventory?",
            tools=(
                ToolDeclaration(
                    name="get_inventory_overview",
                    description="Today's stock by status.",
                    parameters_schema={"type": "object", "properties": {}},
                ),
            ),
            tool_executor=tool_executor,
        )

    assert result is not None
    assert result.final_answer == "You have 1200 filled cylinders."
    assert result.tools_used == ("get_inventory_overview",)
    assert result.tool_turns == 1
    tool_executor.assert_awaited_once_with("get_inventory_overview", {})


async def test_exceeding_the_max_tool_turns_returns_none(gateway: GeminiModelGateway) -> None:
    """A model that keeps requesting tools past the turn cap is treated as a
    provider-level failure, not an infinite loop."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=_tool_call_response(tool_name="get_inventory_overview", args={})
    )
    tool_executor = AsyncMock(return_value={})

    with patch("google.genai.Client", return_value=mock_client):
        result = await gateway.run_with_tools(
            system_prompt="You are helpful.",
            user_prompt="Loop forever.",
            tools=(
                ToolDeclaration(
                    name="get_inventory_overview", description="...", parameters_schema={}
                ),
            ),
            tool_executor=tool_executor,
        )

    assert result is None


async def test_a_provider_exception_degrades_to_none_not_a_raise(
    gateway: GeminiModelGateway,
) -> None:
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=TimeoutError("upstream"))

    with patch("google.genai.Client", return_value=mock_client):
        result = await gateway.run_with_tools(
            system_prompt="You are helpful.",
            user_prompt="Anything.",
            tools=(),
            tool_executor=AsyncMock(),
        )

    assert result is None


async def test_client_is_constructed_once_and_reused(gateway: GeminiModelGateway) -> None:
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=_final_response("ok"))

    with patch("google.genai.Client", return_value=mock_client) as ctor:
        await gateway.run_with_tools(
            system_prompt="s", user_prompt="u", tools=(), tool_executor=AsyncMock()
        )
        await gateway.run_with_tools(
            system_prompt="s", user_prompt="u2", tools=(), tool_executor=AsyncMock()
        )

    ctor.assert_called_once()
