# Plan: WhatsApp AI Customer Assistant

Decision: ADR-054. Tasks: [TASKS.md](./TASKS.md). Status: [STATUS.md](./STATUS.md).

## Requirement

Customers message the agency's WhatsApp Business number and can, in plain
language (English, Hindi or another Indian language), book a cylinder refill,
track and cancel their orders, get an online payment link, and raise a
complaint. Item 3 of the 2026-10-17 request ("full flow like order
management, tracking, payment and all").

## Approach

- **Channel:** Meta's WhatsApp Cloud API directly. One public webhook,
  `GET/POST /api/v1/webhooks/whatsapp` (verify handshake + signed deliveries,
  `X-Hub-Signature-256` HMAC over the raw body). Excluded from the OpenAPI
  contract; it is Meta's contract, not ours.
- **Tenant routing:** each agency sets its own `whatsapp_phone_number_id`
  Tenant Configuration value. `tenant.whatsapp_resolve_tenant_id(text)`
  (SECURITY DEFINER) maps the receiving number to exactly one live tenant, or
  none.
- **Processing:** the webhook only verifies and enqueues an ARQ job per
  message (`job_id = whatsapp:<wamid>`), so Meta gets its 200 at once. The
  job runs `HandleInboundWhatsAppMessageUseCase`.
- **Model:** the existing `ModelGatewayPort` (ADR-045), now with a
  conversation `history` argument and a second adapter for Anthropic Claude
  (`LPG_AI_PROVIDER=anthropic`). Gemini still works.
- **Tools:** nine customer-scoped tools that call the existing order,
  customer, pricing and complaint use cases. Every tool acts only on the
  customer the sender's phone number resolves to.
- **Two-step booking:** `prepare_order` stores a quote; `place_order` only
  accepts a quote created before the current customer message and under 30
  minutes old, so the model can never propose and book in one turn.
- **Payments:** `PaymentLinkPort`. Unconfigured until the Razorpay
  integration supplies an adapter; until then the assistant offers cash/UPI
  on delivery.
- **Safety and cost:** off per agency until `whatsapp_ai_enabled` is set;
  shares `ai_daily_token_budget` with the AI Command Center; every run is in
  `ai.assistant_run` with role `whatsapp_customer`.

## Data

New `messaging` schema: `whatsapp_message` (append-only log, dedupe key
`(tenant_id, direction, wa_message_id)`) and `whatsapp_conversation`
(pending quote per phone). Both RLS-isolated. Migration `a9c2e4f6b8d1`.

## Configuration

Env: `LPG_AI_PROVIDER`, `LPG_ANTHROPIC_API_KEY`, `LPG_ANTHROPIC_MODEL`,
`LPG_ANTHROPIC_EFFORT`, `LPG_WHATSAPP_ACCESS_TOKEN`,
`LPG_WHATSAPP_APP_SECRET`, `LPG_WHATSAPP_VERIFY_TOKEN`,
`LPG_WHATSAPP_GRAPH_API_VERSION`. Tenant config: `whatsapp_ai_enabled`,
`whatsapp_phone_number_id`.
