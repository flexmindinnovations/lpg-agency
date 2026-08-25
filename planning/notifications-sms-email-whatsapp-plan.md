# Email / SMS / WhatsApp / OTP: Status & Implementation Plan

## 1. Current status

| Channel | Status | What exists | What's missing |
|---|---|---|---|
| **In-app (bell/drawer)** | ✅ Complete | Full stack: `InAppNotification` domain aggregate, repository, 4 API endpoints, WebSocket push, 3 frontend libs (bell, drawer, full-page list) | — |
| **Notification log / queue architecture** | ✅ Complete (plumbing only) | `NotificationLog` aggregate with a real status machine (`queued → sent → delivered → failed/retrying → dead_lettered`), ARQ job (`send_notification`) wired to 5 domain events, retry policy (`max_tries=5`) | Real channel adapters — everything downstream of "decide to send" is a stub |
| **Email** | 🔴 Stub only | `EmailChannel` port defined, `LoggingEmailSender`/`StubEmailChannel` just log the message | No provider wired at all |
| **SMS** | 🔴 Stub only | `SmsChannel` port defined, same stub pattern | No provider wired; **India SMS also needs TRAI DLT registration** (see §4) — this is a regulatory step, not just a code change |
| **OTP delivery** (login + order-delivery) | 🔴 Stub only | `LoggingOtpDelivery` — logs the code (extended this session to also stash it in Redis for local/E2E testing, see `order-to-delivery-e2e-checklist.md`) | Real SMS provider — OTP delivery is really "SMS" wearing a different hat |
| **WhatsApp** | ⚪ Not started | Literally just an enum value (`booking_source: "whatsapp"`) in the Order schema — a filter tag, nothing sends or receives anything | Everything — no Business API client, no webhook, no templates. **Explicitly deferred to Phase 2** in `docs/implementation/roadmap.md` (decision A-21) |
| **Templates** | ⚪ Not started | Subject/body are hardcoded Python string dicts in the ARQ job | No template table, no per-tenant customization, no localization |
| **Preferences** (opt-in/opt-out per channel) | ⚪ Not started | — | No UI, no backend model |
| **Push (mobile)** | ⚪ Not started | — | Not mentioned anywhere in the codebase; only relevant if/when a mobile app ships |

**Two known bugs in the existing plumbing** (worth fixing alongside real provider work, not after):

1. **Background-job events are dropped.** `send_notification`'s `SqlAlchemyUnitOfWork` is constructed without an `event_dispatcher`, so `NotificationSent` (fired on every `NotificationLog` status change) has nowhere to go when triggered from the ARQ worker — confirmed in `planning/MODULE_STATUS.md`. Anything that should react to a delivery/failure event (e.g. updating a dashboard metric) silently won't fire today.
2. **"Out for Delivery" notifications are dead code.** The `RouteStatusChanged` handler is a `pass` with a TODO — the event doesn't carry `order_id`, so this notification type is defined (`_should_send_sms` references `out_for_delivery`) but can never actually fire.

## 2. Step-by-step implementation plan

The hard part — domain modeling, the queue, retry logic, event triggers — is already done. What's left is genuinely "plug a real provider into an existing port," not a redesign.

### Step 1 — Pick providers
See §3 below. Recommend: **MSG91 or Twilio for SMS** (MSG91 if optimizing for India-only cost; Twilio if you want one vendor across SMS+WhatsApp+better docs), **Resend or Amazon SES for email** (SES if you want to reuse the AWS credentials already configured for S3-compatible storage).

### Step 2 — Add config
In `backend/src/lpg/config/settings.py`, add provider fields (API key, sender ID/from-address, and for SMS the DLT template IDs — see §4) — same pattern already used for `otp_length`/`otp_ttl_seconds`. Add to `.env.example` and `backend/.env`. Gate real-provider usage the same way `otp_delivery_dev_mode` already gates the stub — real credentials simply shouldn't resolve to anything usable in `local`.

### Step 3 — Add SDK dependencies
`uv add` whichever SDKs the chosen providers ship (e.g. `boto3`/`aioboto3` for SES — already a dependency; `httpx` calls work fine for most SMS REST APIs without a dedicated SDK, since `httpx` is presumably already a dependency for this FastAPI app).

### Step 4 — Implement real channel adapters
New classes implementing the existing `EmailChannel`/`SmsChannel`/`OtpDeliveryPort` protocols — e.g. `infrastructure/notification/ses_email_channel.py`, `infrastructure/notification/msg91_sms_channel.py`. Return the provider's message ID from `send()` so it can be persisted (currently `provider_message_id` is always `None` — see `NotificationSent`'s docstring).

### Step 5 — Wire dependency injection
Swap the dependency-provider functions (`get_email_sender()`, `get_sms_channel()`, `get_otp_delivery()` in `api/v1/dependencies/identity.py` and wherever `SmsChannel`/`EmailChannel` are resolved) to return the real adapter when configured, falling back to the stub in `local`/test — same shape as the `otp_delivery_dev_mode` gate already in place.

### Step 6 — Add delivery-status webhooks
Most providers POST delivery/bounce/failure callbacks. Add an endpoint (e.g. `POST /webhooks/sms-status`, `POST /webhooks/email-status`) that updates the matching `NotificationLog.status` — this is what makes `delivered`/`failed` actually mean something instead of always sitting at `sent`.

### Step 7 — Fix the two known plumbing gaps (§1)
Do this alongside Step 5, not as an afterthought — wiring a real provider makes the dropped-events gap actually matter (you'll want to know when a real SMS fails).

### Step 8 — Register for TRAI DLT (India SMS — mandatory, not optional)
See §4. This has a lead time (days, sometimes longer for entity verification) — start it in parallel with Steps 2-3, not after code is ready, or the code will be ready and nothing will actually deliver to Indian numbers.

### Step 9 — Testing
- Unit: mock the channel port, same as today.
- Integration: most providers have a sandbox/test mode (Twilio's magic test numbers, MSG91's test route) — use it, don't burn real SMS credits in CI.
- End-to-end: the OTP dev-inbox endpoint added this session (`GET /api/v1/dev/otp-inbox/{phone}`, gated to non-production) can stay as-is for local/CI — real providers only need to be live in staging/production, where that endpoint is already unreachable.

### Step 10 — (Later, optional) Templates + preferences
Not currently scoped anywhere, but natural next steps once real sending exists: a `notification.template` table (subject/body per `notification_type` per tenant, replacing the hardcoded Python dicts), and a `notification.preference` table + settings UI for per-customer/per-staff opt-in/opt-out per channel.

### WhatsApp — separate, bigger track
Deferred to Phase 2 by an existing product decision (A-21) — don't build this incidentally while doing SMS/email. If/when it's picked up: register a WhatsApp Business Account, get a phone number verified with Meta (or go through a BSP like Gupshup/MSG91 who handle that for you), get message templates pre-approved (WhatsApp requires template approval for any business-initiated message outside a 24-hour customer-service window), then implement the same `NotificationLog`-backed pattern with a new `WhatsAppChannel` port.

## 3. Free / low-cost provider options

Prices and free-tier terms change often — verify current numbers on each provider's site before committing budget or code to one. This app is India-based (Telangana addresses, +91 numbers, INR), so SMS/WhatsApp recommendations lean toward providers with strong India routes and DLT support built in.

### Email
| Provider | Free tier (approx.) | Notes |
|---|---|---|
| **Resend** | ~3,000 emails/mo, 100/day | Modern API, good Python support, easiest DX |
| **Brevo** (ex-Sendinblue) | ~300 emails/day forever | Also bundles SMS — one vendor for both |
| **Amazon SES** | Not free, but ~$0.10/1,000 emails | You already use `aioboto3` for S3-compatible storage — same AWS credential story, minimal new tooling |
| **SendGrid** | ~100 emails/day forever | Long-established, solid deliverability reputation |

### SMS (India-focused)
| Provider | Free tier (approx.) | Notes |
|---|---|---|
| **MSG91** | Free trial credit | India-focused, handles DLT registration/templates through their own dashboard, also offers WhatsApp + email — could consolidate SMS+WhatsApp on one vendor |
| **Fast2SMS** | Free/cheap DLT routes | India-focused, simple REST API |
| **Twilio** | ~$15 trial credit, no forever-free tier | Best docs/SDK, but pricier per-SMS on India routes than local providers; still handles DLT-compliant sending |
| **AWS SNS** | Pay-per-SMS, no free tier | You'd still need to handle DLT registration yourself; only worth it if you want everything on AWS |

### WhatsApp (when Phase 2 arrives)
| Provider | Free tier (approx.) | Notes |
|---|---|---|
| **Meta WhatsApp Business Platform (direct)** | Limited free conversations/month | Requires Meta Business verification yourself |
| **Gupshup** | Free sandbox for testing | Popular India BSP, handles Meta verification/onboarding for you |
| **MSG91** | Bundled with SMS/email | One vendor if already using them for SMS |
| **Twilio WhatsApp API** | Free sandbox (joined test number only) | Production needs Business verification + per-message cost |

### Push (mobile — only relevant once a mobile app exists)
| Provider | Free tier | Notes |
|---|---|---|
| **Firebase Cloud Messaging** | Free, unlimited | Industry standard, no reason to pay for anything else here |

## 4. TRAI DLT — the part that's easy to miss

India's telecom regulator (TRAI) requires all commercial SMS senders to register as an entity on the **Distributed Ledger Technology (DLT)** platform and pre-register every message template before sending. This is independent of which SMS provider you pick — **skipping it means SMS silently fails to deliver to Indian numbers**, regardless of provider or code correctness (already flagged as a tracked gap in `docs/research/feature-gap-analysis.md`, item R22). MSG91 and most India-focused providers have built-in tooling to walk through DLT registration; Twilio/AWS SNS do not — you'd handle it separately via one of the DLT platforms (e.g. Jio/Airtel/Vodafone's DLT portals) yourself.
