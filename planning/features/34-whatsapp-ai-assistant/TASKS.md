# Tasks: WhatsApp AI Customer Assistant

Plan: [PLAN.md](./PLAN.md).

## Done (2026-10-17)

- [x] `ModelGatewayPort.run_with_tools` takes conversation `history`; Gemini adapter maps it.
- [x] Anthropic Claude adapter + factory branch + settings; import-linter contract keeps the SDK in `infrastructure.ai`.
- [x] Migration `a9c2e4f6b8d1`: `messaging.whatsapp_message`, `messaging.whatsapp_conversation`, tenant resolver function.
- [x] Conversation repository (deduplicated inbound, outbound log, pending quote).
- [x] Webhook router (verify handshake, signature check, enqueue) and ARQ job.
- [x] Meta Cloud API sender (stub when no token is configured).
- [x] Nine customer tools and `HandleInboundWhatsAppMessageUseCase`.
- [x] Tenant config keys `whatsapp_ai_enabled`, `whatsapp_phone_number_id` (backend + dashboard settings page).
- [x] Unit tests (adapter, webhook parsing, assistant flows) and integration tests (routing, dedupe, booking end to end, RLS, webhook).
- [x] ADR-052, env templates, module status.

## Follow-ups (not started)

- [ ] Razorpay `PaymentLinkPort` adapter wrapping `CreateOrderPaymentLinkUseCase` from the Razorpay PR (#12), once it merges. Only the adapter and the job wiring change; the tool and prompt already handle links.
- [ ] Proactive order-status notifications through approved message templates (outside the 24-hour window).
- [ ] A separate token budget for WhatsApp, if sharing `ai_daily_token_budget` with the AI Command Center proves too coarse.
- [ ] Retention policy for `messaging.whatsapp_message`.
- [ ] Self-registration of new customers over WhatsApp (today unknown numbers get a fixed reply).
- [ ] Media messages (images of a leak, documents) beyond a bracketed placeholder.
- [ ] Dashboard view of WhatsApp conversations for staff.
- [ ] Try against a real Meta test number and UAT.
