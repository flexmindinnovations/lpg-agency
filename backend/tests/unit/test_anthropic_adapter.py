"""Unit tests for `AnthropicModelGateway` (ADR-054): the manual tool-calling
loop, history handling and graceful degradation, against a mocked
`anthropic.AsyncAnthropic`. No real network call is made."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lpg.application.ai.ports import ConversationTurn, ToolDeclaration
from lpg.infrastructure.ai.anthropic_adapter import AnthropicModelGateway


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=2,
        cache_creation_input_tokens=None,
    )


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _response(*content: SimpleNamespace, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        usage=_usage(),
        model="claude-opus-5-5",
    )


def _tool_use(name: str, tool_input: dict[str, Any], tool_id: str = "toolu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=tool_id)


_TOOL = ToolDeclaration(
    name="track_order",
    description="Track an order.",
    parameters_schema={"type": "object", "properties": {}},
)


def _client(*responses: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.beta.messages.create = AsyncMock(side_effect=list(responses))
    return client


@pytest.fixture
def gateway() -> AnthropicModelGateway:
    return AnthropicModelGateway(api_key="test-key", model="claude-opus-5-5")


async def test_returns_final_answer_without_tool_calls(gateway: AnthropicModelGateway) -> None:
    client = _client(_response(_text("Hello! How can I help?")))
    with patch("anthropic.AsyncAnthropic", return_value=client):
        result = await gateway.run_with_tools(
            system_prompt="sys",
            user_prompt="hi",
            tools=(_TOOL,),
            tool_executor=AsyncMock(),
        )

    assert result is not None
    assert result.final_answer == "Hello! How can I help?"
    assert result.provider == "anthropic"
    assert result.model == "claude-opus-5-5"
    assert result.tool_turns == 0
    assert result.prompt_tokens == 12  # input + cache read
    assert result.completion_tokens == 5
    kwargs = client.beta.messages.create.await_args.kwargs
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["tools"][0]["name"] == "track_order"
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


async def test_runs_a_tool_and_feeds_the_result_back(gateway: AnthropicModelGateway) -> None:
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    first = _response(
        thinking, _tool_use("track_order", {"order_number": "ORD-1"}), stop_reason="tool_use"
    )
    client = _client(first, _response(_text("It is out for delivery.")))
    executor = AsyncMock(return_value={"status": "out_for_delivery"})

    with patch("anthropic.AsyncAnthropic", return_value=client):
        result = await gateway.run_with_tools(
            system_prompt="sys",
            user_prompt="where is ORD-1?",
            tools=(_TOOL,),
            tool_executor=executor,
        )

    assert result is not None
    assert result.final_answer == "It is out for delivery."
    assert result.tools_used == ("track_order",)
    assert result.tool_turns == 1
    executor.assert_awaited_once_with("track_order", {"order_number": "ORD-1"})

    second_messages = client.beta.messages.create.await_args_list[1].kwargs["messages"]
    # The assistant turn is passed back unchanged, thinking block included.
    assert second_messages[1] == {"role": "assistant", "content": first.content}
    tool_result = second_messages[2]["content"][0]
    assert tool_result["tool_use_id"] == "toolu_1"
    assert json.loads(tool_result["content"]) == {"status": "out_for_delivery"}
    assert tool_result["is_error"] is False


async def test_tool_error_is_flagged(gateway: AnthropicModelGateway) -> None:
    client = _client(
        _response(_tool_use("track_order", {}), stop_reason="tool_use"),
        _response(_text("Sorry.")),
    )
    with patch("anthropic.AsyncAnthropic", return_value=client):
        await gateway.run_with_tools(
            system_prompt="sys",
            user_prompt="x",
            tools=(_TOOL,),
            tool_executor=AsyncMock(return_value={"error": "not found"}),
        )
    messages = client.beta.messages.create.await_args_list[1].kwargs["messages"]
    assert messages[-1]["content"][0]["is_error"] is True


async def test_history_drops_leading_assistant_turns(gateway: AnthropicModelGateway) -> None:
    client = _client(_response(_text("ok")))
    with patch("anthropic.AsyncAnthropic", return_value=client):
        await gateway.run_with_tools(
            system_prompt="sys",
            user_prompt="and now?",
            tools=(),
            tool_executor=AsyncMock(),
            history=[
                ConversationTurn(role="assistant", text="Welcome!"),
                ConversationTurn(role="user", text="book a cylinder"),
                ConversationTurn(role="assistant", text="Which size?"),
            ],
        )
    messages = client.beta.messages.create.await_args.kwargs["messages"]
    assert messages == [
        {"role": "user", "content": "book a cylinder"},
        {"role": "assistant", "content": "Which size?"},
        {"role": "user", "content": "and now?"},
    ]


async def test_refusal_returns_none(gateway: AnthropicModelGateway) -> None:
    client = _client(_response(stop_reason="refusal"))
    with patch("anthropic.AsyncAnthropic", return_value=client):
        result = await gateway.run_with_tools(
            system_prompt="sys", user_prompt="x", tools=(), tool_executor=AsyncMock()
        )
    assert result is None


async def test_provider_exception_returns_none(gateway: AnthropicModelGateway) -> None:
    client = MagicMock()
    client.beta.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("anthropic.AsyncAnthropic", return_value=client):
        result = await gateway.run_with_tools(
            system_prompt="sys", user_prompt="x", tools=(), tool_executor=AsyncMock()
        )
    assert result is None


async def test_endless_tool_calls_stop_at_the_cap(gateway: AnthropicModelGateway) -> None:
    client = MagicMock()
    client.beta.messages.create = AsyncMock(
        return_value=_response(_tool_use("track_order", {}), stop_reason="tool_use")
    )
    with patch("anthropic.AsyncAnthropic", return_value=client):
        result = await gateway.run_with_tools(
            system_prompt="sys",
            user_prompt="x",
            tools=(_TOOL,),
            tool_executor=AsyncMock(return_value={}),
        )
    assert result is None
    assert client.beta.messages.create.await_count == 6
