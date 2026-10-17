"""`ModelGatewayPort` backed by Anthropic's Messages API (`anthropic`).

Drives the tool-calling loop manually rather than through the SDK's beta
tool runner, for the same reason `GeminiModelGateway` does: `tool_executor`
is a plain `(name, arguments) -> dict` callback the application layer
supplies, never an SDK-specific object, so the port stays vendor-neutral.

Loop shape (from the SDK's documented manual agentic loop): append the
assistant's whole `content` (thinking and `tool_use` blocks included,
unchanged), then one `user` message carrying every `tool_result` for that
turn. Thinking blocks must be passed back as-is, which is why `content` is
appended rather than rebuilt.

Server-side refusal fallback (`fallbacks="default"`) is opted into on every
request, so a safety-classifier false positive on a benign customer message
is retried on Anthropic's recommended fallback model instead of failing the
conversation. A refusal that survives the fallback chain is a `None`
(provider error), like any other unusable response.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Literal

from lpg.application.ai.ports import AgentRunResult, ToolDeclaration, ToolExecutor
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from anthropic import AsyncAnthropic

    from lpg.application.ai.ports import ConversationTurn

_logger = get_logger(__name__)

#: A WhatsApp turn can legitimately chain a few lookups (account, options,
#: quote) before answering, so this sits above Gemini's 4. Still capped, so a
#: looping model ends in a visible provider error rather than unbounded spend.
_MAX_TOOL_TURNS = 6

#: Replies are short chat messages; this leaves room for adaptive thinking.
_MAX_TOKENS = 4096

_FALLBACK_BETA = "server-side-fallback-2026-07-01"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class AnthropicModelGateway:
    """Client constructed lazily, once per process, mirroring
    `GeminiModelGateway`: an occasional advisory dependency should not slow
    every server boot."""

    def __init__(self, *, api_key: str, model: str, effort: Effort = "low") -> None:
        self._api_key = api_key
        self._model = model
        self._effort: Effort = effort
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def run_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: tuple[ToolDeclaration, ...],
        tool_executor: ToolExecutor,
        history: Sequence[ConversationTurn] = (),
    ) -> AgentRunResult | None:
        started = time.monotonic()
        try:
            client = self._get_client()
            tool_params: list[Any] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters_schema,
                }
                for tool in tools
            ]
            messages: list[Any] = _history_messages(history)
            messages.append({"role": "user", "content": user_prompt})

            tools_used: list[str] = []
            prompt_tokens = 0
            completion_tokens = 0

            for tool_turn in range(_MAX_TOOL_TURNS):
                response = await client.beta.messages.create(
                    model=self._model,
                    max_tokens=_MAX_TOKENS,
                    # The system prompt and tool list are identical on every
                    # turn and every conversation, so they are the cacheable
                    # prefix.
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=tool_params,
                    messages=messages,
                    output_config={"effort": self._effort},
                    betas=[_FALLBACK_BETA],
                    fallbacks="default",
                )
                usage = response.usage
                prompt_tokens += (
                    usage.input_tokens
                    + (usage.cache_read_input_tokens or 0)
                    + (usage.cache_creation_input_tokens or 0)
                )
                completion_tokens += usage.output_tokens

                if response.stop_reason == "refusal":
                    _logger.warning("ai_gateway_refusal", model=response.model)
                    return None

                tool_uses = [block for block in response.content if block.type == "tool_use"]
                if not tool_uses:
                    answer = "".join(
                        block.text for block in response.content if block.type == "text"
                    ).strip()
                    return AgentRunResult(
                        final_answer=answer,
                        tools_used=tuple(tools_used),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tool_turns=tool_turn,
                        provider="anthropic",
                        model=response.model,
                    )

                messages.append({"role": "assistant", "content": response.content})
                results: list[Any] = []
                for block in tool_uses:
                    tools_used.append(block.name)
                    arguments = block.input if isinstance(block.input, dict) else {}
                    result = await tool_executor(block.name, dict(arguments))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                            "is_error": "error" in result,
                        }
                    )
                messages.append({"role": "user", "content": results})

            _logger.warning("ai_gateway_max_tool_turns_exceeded", max_turns=_MAX_TOOL_TURNS)
            return None
        except Exception:
            _logger.exception(
                "ai_gateway_provider_error",
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            return None


def _history_messages(history: Sequence[ConversationTurn]) -> list[Any]:
    """Earlier turns as Messages API messages. The API requires the first
    message to be from the user, so leading assistant turns (a greeting the
    business sent before the customer wrote) are dropped; consecutive
    same-role turns are allowed and merged by the API."""
    turns = list(history)
    while turns and turns[0].role == "assistant":
        turns.pop(0)
    return [{"role": turn.role, "content": turn.text} for turn in turns if turn.text.strip()]
