"""`HandleInboundWhatsAppMessageUseCase` (ADR-055): one customer message in,
one reply out.

Order of work, each step only if the one before allows it:

1. Record the message (deduplicated on Meta's message id, since Meta retries
   webhook deliveries) and read the conversation so far.
2. If the agency has not switched the assistant on (`whatsapp_ai_enabled`),
   stop: the message is logged for staff, nothing is sent.
3. If the number belongs to no customer, send a fixed reply. No model call.
4. If today's AI token budget (`ai_daily_token_budget`, shared with the AI
   Command Center) is spent, send a fixed reply. No model call.
5. Run the model with the conversation history and the customer tools.
6. Send the reply, then log it and the run in one transaction.

The fixed replies keep a customer from being left on read whenever the
assistant cannot help.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from lpg.application.ai.ports import AssistantRun, ConversationTurn
from lpg.application.ai.use_cases import DEFAULT_AI_DAILY_TOKEN_BUDGET
from lpg.application.common.config import is_truthy_config_value
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)
from lpg.application.whatsapp.tools import (
    CUSTOMER_TOOLS,
    CustomerToolContext,
    execute_customer_tool,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from lpg.application.ai.ports import AgentRunResult, ModelGatewayPort
    from lpg.application.whatsapp.ports import (
        ConversationEntry,
        InboundWhatsAppMessage,
        PaymentLinkPort,
        WhatsAppScope,
        WhatsAppSenderPort,
    )
    from lpg.application.whatsapp.tools import WhatsAppScopeFactory

#: Tenant Configuration key switching the assistant on. Off by default, like
#: `ai_gateway_enabled`: an agency opts in deliberately.
WHATSAPP_AI_ENABLED_KEY = "whatsapp_ai_enabled"

#: Meta allows free-form replies for 24 hours after the customer's last
#: message, which is also a natural boundary for "this conversation".
HISTORY_WINDOW = timedelta(hours=24)
HISTORY_LIMIT = 20

#: Recorded on `ai.assistant_run.role`, to tell these runs apart from AI
#: Command Center runs in the shared ledger.
ASSISTANT_RUN_ROLE = "whatsapp_customer"

UNKNOWN_CUSTOMER_REPLY = (
    "Hello! We couldn't find a customer account registered with this WhatsApp number. "
    "Please contact the agency to register, or message us from the number on your "
    "LPG connection."
)
UNAVAILABLE_REPLY = (
    "Sorry, our WhatsApp assistant is unavailable right now. Please try again later or "
    "call the agency directly."
)

_SYSTEM_PROMPT = (
    "You are the WhatsApp assistant of an LPG gas distributor (agency) in India, "
    "talking to one of its registered customers. You help them book cylinder "
    "refills, track and cancel orders, pay online, and raise complaints, using "
    "only the tools provided. Never guess an order status, price or address you "
    "could look up.\n\n"
    "Booking a refill: find the cylinder option (list_cylinder_options) and the "
    "delivery address (get_my_account) if unclear, call prepare_order, then read "
    "the quote back and ask the customer to confirm. Call place_order only in a "
    "later turn, after the customer clearly confirms. Prices from the tools are "
    "estimates until the agency confirms the order.\n\n"
    "Style: this is WhatsApp. Reply in the customer's language (English, Hindi or "
    "another Indian language as they write), in short plain sentences. Use "
    "WhatsApp formatting only (*bold*, line breaks, simple numbered lists); no "
    "markdown headings or tables. Show amounts as ₹.\n\n"
    "Safety: for a gas leak or smell of gas, tell the customer immediately to "
    "turn off the regulator, open doors and windows, avoid switches and flames, "
    "and call the LPG emergency helpline 1906, then raise a complaint. You can "
    "only act on this customer's own account; politely refuse requests about "
    "anyone else or unrelated topics. If a tool returns an error, explain it "
    "simply and suggest a next step."
)


@dataclass(frozen=True, slots=True)
class HandleInboundWhatsAppMessageResult:
    outcome: Literal[
        "duplicate",
        "assistant_disabled",
        "unknown_customer",
        "budget_exceeded",
        "provider_error",
        "answered",
    ]
    reply: str | None


@dataclass(frozen=True, slots=True)
class _Preflight:
    enabled: bool
    customer_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    budget_left: bool
    history: list[ConversationEntry]


class HandleInboundWhatsAppMessageUseCase:
    def __init__(
        self,
        *,
        tenant_id: uuid.UUID,
        gateway: ModelGatewayPort,
        sender: WhatsAppSenderPort,
        scope_factories: Callable[[uuid.UUID | None], WhatsAppScopeFactory],
        payment_links: PaymentLinkPort,
    ) -> None:
        """`scope_factories(actor_id)` returns a scope factory whose writes
        are audited as `actor_id`; `None` before the customer is known."""
        self._tenant_id = tenant_id
        self._gateway = gateway
        self._sender = sender
        self._scope_factories = scope_factories
        self._scope_factory = scope_factories(None)
        self._payment_links = payment_links

    async def execute(self, message: InboundWhatsAppMessage) -> HandleInboundWhatsAppMessageResult:
        turn_started_at = datetime.now(UTC)
        async with self._scope_factory() as scope:
            history = await scope.conversations.list_recent(
                message.from_phone, since=turn_started_at - HISTORY_WINDOW, limit=HISTORY_LIMIT
            )
            if not await scope.conversations.record_inbound(message):
                await scope.unit_of_work.rollback()
                return HandleInboundWhatsAppMessageResult(outcome="duplicate", reply=None)
            preflight = await self._preflight(scope, message, history)
            await scope.unit_of_work.commit()

        if not preflight.enabled:
            return HandleInboundWhatsAppMessageResult(outcome="assistant_disabled", reply=None)
        if preflight.customer_id is None or preflight.actor_id is None:
            await self._reply(message, UNKNOWN_CUSTOMER_REPLY)
            return HandleInboundWhatsAppMessageResult(
                outcome="unknown_customer", reply=UNKNOWN_CUSTOMER_REPLY
            )
        if not preflight.budget_left:
            await self._reply(message, UNAVAILABLE_REPLY, run_status="budget_exceeded")
            return HandleInboundWhatsAppMessageResult(
                outcome="budget_exceeded", reply=UNAVAILABLE_REPLY
            )

        ctx = CustomerToolContext(
            tenant_id=self._tenant_id,
            customer_id=preflight.customer_id,
            customer_phone=message.from_phone,
            actor_id=preflight.actor_id,
            turn_started_at=turn_started_at,
            scope_factory=self._scope_factories(preflight.actor_id),
            payment_links=self._payment_links,
        )

        async def tool_executor(name: str, arguments: dict[str, object]) -> dict[str, object]:
            return await execute_customer_tool(ctx, name, dict(arguments))

        started = time.monotonic()
        result = await self._gateway.run_with_tools(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=message.text,
            tools=tuple(tool.declaration for tool in CUSTOMER_TOOLS),
            tool_executor=tool_executor,
            history=[
                ConversationTurn(
                    role="user" if entry.direction == "inbound" else "assistant",
                    text=entry.body,
                )
                for entry in preflight.history
            ],
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        if result is None or not result.final_answer:
            await self._reply(
                message,
                UNAVAILABLE_REPLY,
                run_status="provider_error",
                run=result,
                latency_ms=latency_ms,
                actor_id=preflight.actor_id,
            )
            return HandleInboundWhatsAppMessageResult(
                outcome="provider_error", reply=UNAVAILABLE_REPLY
            )

        await self._reply(
            message,
            result.final_answer,
            run_status="success",
            run=result,
            latency_ms=latency_ms,
            actor_id=preflight.actor_id,
        )
        return HandleInboundWhatsAppMessageResult(outcome="answered", reply=result.final_answer)

    async def _preflight(
        self,
        scope: WhatsAppScope,
        message: InboundWhatsAppMessage,
        history: list[ConversationEntry],
    ) -> _Preflight:
        enabled_config = await self._config(scope, WHATSAPP_AI_ENABLED_KEY)
        enabled = enabled_config is not None and is_truthy_config_value(enabled_config)
        if not enabled:
            return _Preflight(False, None, None, budget_left=False, history=history)

        customer = await scope.customers.get_by_phone(message.from_phone)
        if customer is None:
            return _Preflight(True, None, None, budget_left=False, history=history)

        budget_config = await self._config(scope, "ai_daily_token_budget")
        budget = DEFAULT_AI_DAILY_TOKEN_BUDGET
        if budget_config is not None:
            try:
                budget = int(budget_config)
            except (TypeError, ValueError):
                budget = DEFAULT_AI_DAILY_TOKEN_BUDGET
        used_today = await scope.assistant_runs.get_todays_token_usage()
        return _Preflight(
            enabled=True,
            customer_id=customer.id,
            actor_id=customer.identity_user_id or customer.id,
            budget_left=used_today < budget,
            history=history,
        )

    async def _config(self, scope: WhatsAppScope, key: str) -> Any:
        config = await GetEffectiveTenantConfigurationUseCase(scope.tenant_configuration).execute(
            GetEffectiveTenantConfigurationQuery(tenant_id=self._tenant_id, config_key=key)
        )
        return config.config_value if config is not None else None

    async def _reply(
        self,
        message: InboundWhatsAppMessage,
        body: str,
        *,
        run_status: str | None = None,
        run: AgentRunResult | None = None,
        latency_ms: int | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> None:
        """Sends `body`, then logs the outbound message (and, when a model
        run was attempted or refused, its ledger row) in one transaction.
        Sending first means the log records what actually happened."""
        wa_message_id = await self._sender.send_text(
            phone_number_id=message.phone_number_id, to=message.from_phone, body=body
        )
        async with self._scope_factory() as scope:
            await scope.conversations.record_outbound(
                to_phone=message.from_phone,
                body=body,
                wa_message_id=wa_message_id,
                status="sent" if wa_message_id is not None else "failed",
            )
            if run_status is not None:
                await scope.assistant_runs.add(
                    AssistantRun(
                        id=scope.assistant_runs.next_id(),
                        tenant_id=self._tenant_id,
                        user_id=actor_id,
                        role=ASSISTANT_RUN_ROLE,
                        question=message.text,
                        tools_used=list(run.tools_used) if run else [],
                        provider=run.provider if run else "",
                        model=run.model if run else "",
                        prompt_tokens=run.prompt_tokens if run else 0,
                        completion_tokens=run.completion_tokens if run else 0,
                        tool_turns=run.tool_turns if run else 0,
                        latency_ms=latency_ms,
                        status=run_status,
                        error_message=(
                            "The model gateway returned no answer."
                            if run_status == "provider_error"
                            else None
                        ),
                        correlation_id=message.wa_message_id[:100],
                        created_at=datetime.now(UTC),
                    )
                )
            await scope.unit_of_work.commit()
