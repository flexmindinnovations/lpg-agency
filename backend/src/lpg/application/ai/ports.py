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
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


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
    calling loop that ended in a final natural-language answer.

    Carries its own `provider`/`model` rather than the caller supplying
    them: the use case that calls this port is provider-agnostic by design
    (that's the whole point of the abstraction), so it has no business
    knowing which adapter answered — only the adapter itself does."""

    final_answer: str
    tools_used: tuple[str, ...]
    prompt_tokens: int
    completion_tokens: int
    tool_turns: int
    provider: str
    model: str


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


@dataclass(frozen=True, slots=True)
class AssistantRun:
    """One `POST /ai/ask` call, append-only — same "plain entity, not an
    `AggregateRoot`" shape as `WeighmentRecord`/`ProofOfDeliveryEntry`: it
    never changes after creation, so there's no invariant-protecting
    aggregate to model, just a record of what happened. Written inside the
    same UoW as everything else in `AskAiAssistantUseCase`, which rides
    `AuditRecorder`'s existing generic `before_flush` hook for a free audit
    trail — no bespoke audit-write path needed.

    Deliberately does not store the raw question/answer text bodies beyond
    what this slice actually uses — full prompt/response capture for
    evaluation is Phase 21's own later scope (a DPDP retention-policy
    question, not just a schema one), explicitly deferred, not silently
    dropped.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    role: str | None
    question: str
    tools_used: list[str]
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    tool_turns: int
    latency_ms: int | None
    status: str
    error_message: str | None
    correlation_id: str | None
    created_at: datetime


@runtime_checkable
class AssistantRunRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def add(self, run: AssistantRun) -> None: ...

    async def get_todays_token_usage(self) -> int:
        """Sum of `prompt_tokens + completion_tokens` across every run for
        the current tenant (RLS-scoped, same as `get_balance_summary()`'s
        own convention — no explicit `tenant_id` filter needed) since the
        start of today (UTC). The pre-call budget check reads this before
        touching the gateway."""
        ...
