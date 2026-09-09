"""`ModelGatewayPort` backed by Gemini's native function-calling API
(`google-genai`).

Drives the tool-calling loop manually (not the SDK's own "automatic function
calling," which expects real Python callables registered on the config) so
the loop stays framework-agnostic at the port boundary: `tool_executor` is a
plain `(name, arguments) -> dict` callback the *application layer* supplies
(`AskAiAssistantUseCase`), never a Gemini-specific object. The turn/role
shape below (append the model's own function-call turn, then a
`role="user"` turn carrying the function response) matches this SDK's own
internal automatic-function-calling implementation
(`google.genai.chats._closure_.chat` — verified by reading the installed
package's source, not guessed) — mirroring a real, working reference rather
than inventing a plausible-looking shape.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lpg.application.ai.ports import AgentRunResult, ToolDeclaration, ToolExecutor
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from google.genai import Client

_logger = get_logger(__name__)

#: Capped so a model that keeps requesting tools (or a loop-inducing bug)
#: can't burn tokens indefinitely on one request — a `None` (provider-error)
#: result past this point is a safe, visible failure, not a hang.
_MAX_TOOL_TURNS = 4


class GeminiModelGateway:
    """Client constructed lazily, once per process — mirrors
    `RapidOcrDocumentAdapter`'s lazy-engine pattern (`infrastructure/ocr/
    rapidocr_adapter.py`): this is an occasional, advisory feature, not a
    critical-path dependency, so there's no reason to slow down every
    server boot for it."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def run_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: tuple[ToolDeclaration, ...],
        tool_executor: ToolExecutor,
    ) -> AgentRunResult | None:
        from google.genai import types

        started = time.monotonic()
        try:
            client = self._get_client()
            declarations = [
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters_json_schema=tool.parameters_schema,
                )
                for tool in tools
            ]
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            )
            contents: list[types.Content] = [
                types.Content(role="user", parts=[types.Part(text=user_prompt)])
            ]

            tools_used: list[str] = []
            prompt_tokens = 0
            completion_tokens = 0

            for tool_turn in range(_MAX_TOOL_TURNS):
                response = await client.aio.models.generate_content(
                    model=self._model,
                    # `list[Content]` is a valid `ContentListUnion` at
                    # runtime, but mypy's list invariance won't accept it as
                    # a subtype of `list[Content | str | Image | ...]` — the
                    # SDK's own stub shape, not a real type error here.
                    contents=contents,  # type: ignore[arg-type]
                    config=config,
                )
                usage = response.usage_metadata
                if usage is not None:
                    prompt_tokens += usage.prompt_token_count or 0
                    completion_tokens += usage.candidates_token_count or 0

                calls = response.function_calls
                if not calls:
                    return AgentRunResult(
                        final_answer=response.text or "",
                        tools_used=tuple(tools_used),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tool_turns=tool_turn,
                        provider="gemini",
                        model=self._model,
                    )

                candidates = response.candidates
                if not candidates or candidates[0].content is None:
                    # A tool call with no content to append back is a
                    # malformed response, not a normal outcome.
                    _logger.warning("ai_gateway_missing_candidate_content")
                    return None
                contents.append(candidates[0].content)

                result_parts = []
                for call in calls:
                    name = call.name or ""
                    tools_used.append(name)
                    result = await tool_executor(name, dict(call.args or {}))
                    result_parts.append(
                        types.Part.from_function_response(name=name, response=result)
                    )
                contents.append(types.Content(role="user", parts=result_parts))

            _logger.warning("ai_gateway_max_tool_turns_exceeded", max_turns=_MAX_TOOL_TURNS)
            return None
        except Exception:
            _logger.exception(
                "ai_gateway_provider_error",
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            return None
