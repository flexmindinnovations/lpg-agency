"""`ModelGatewayPort` — the single outbound seam for every AI model call.

One provider today (Gemini), swappable without touching anything above this
port: `infrastructure/ai/factory.py` picks the adapter class from
`Settings.ai_provider`, and no other module imports a vendor AI SDK (matches
`DocumentOcrPort`/`FileStorage`'s existing port/adapter shape exactly).

Tool-calling, not plain structured-output generation — the only capability
the AI Command Center (ADR-045) needs. A `generate()` method with no tools is
deliberately not added here; add one only when a future feature actually
needs it (YAGNI).

The port never sees what a "tool" means business-wise — `tool_executor` is a
plain callback the *application layer* supplies (see `application/ai/tools.py`
and `AskAiAssistantUseCase`). This keeps infrastructure speaking only the
wire protocol; the application layer owns which real Python function each
tool name maps to, and enforces authorization before ever calling it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ToolDeclaration:
    """One tool the model may choose to call — name/description/parameter
    schema only. Every v1 tool is zero-argument (`parameters_schema`'s
    `properties` is always `{}`) — see ADR-045 for why."""

    name: str
    description: str
    parameters_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """The outcome of one `run_with_tools` call — a possibly-multi-turn tool
    calling loop that ended in a final natural-language answer."""

    final_answer: str
    tools_used: tuple[str, ...]
    prompt_tokens: int
    completion_tokens: int
    tool_turns: int


#: `(tool_name, arguments) -> JSON-safe result dict`. Supplied by the
#: application layer; the adapter never inspects what it does, only calls it
#: when the model requests a tool and feeds the result back.
ToolExecutor = Callable[[str, dict[str, object]], Awaitable[dict[str, object]]]


@runtime_checkable
class ModelGatewayPort(Protocol):
    async def run_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: tuple[ToolDeclaration, ...],
        tool_executor: ToolExecutor,
    ) -> AgentRunResult | None:
        """Drives the model's native function-calling loop: the model may
        request zero or more tool calls (via `tool_executor`, one at a time,
        results fed back automatically) before producing a final answer.

        Returns `None` only on a genuine provider-level failure (timeout,
        safety-filter block, API error) — an advisory feature must never
        raise because a vendor API hiccuped. Kill-switch and budget checks
        never reach this port at all; they're the caller's job
        (`AskAiAssistantUseCase`), matching how `weighment_gate_enabled` is
        checked in the use case, not a lower layer.
        """
        ...
