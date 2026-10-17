# Plan: SMS Gateway (OTP + Order Updates)

## Goal

Login OTPs, delivery OTPs and order status SMS were never sent: OTPs went to `LoggingOtpDelivery` (log line + non-production dev inbox) and order SMS to `StubSmsChannel` (log line). Send them for real through an Indian, DLT-compliant provider, behind the existing ports so another provider can be swapped in. Requested 2026-10-17; provider default **MSG91** (ADR-052).

## Design

- **Application**
  - `SmsTemplate` enum (`application/notification/ports.py`): every SMS the platform sends. DLT forbids free text, so each message is a registered template.
  - `SmsChannel.send(to, body, template, variables)`; `body` is the plain-text rendering kept for the notification log and free-text providers. `SmsDeliveryError` on rejection/outage.
  - `OtpDeliveryPort.send(phone, code, *, purpose="login" | "delivery")` so the delivery OTP uses its own wording. `DepartOrderUseCase` passes `purpose="delivery"` and no longer fails the departure if the SMS can't be sent (it is already committed).
- **Infrastructure**
  - `Msg91SmsChannel` (`infrastructure/channels/sms_channel.py`): `POST {base}/api/v5/flow` with `template_id` and one recipient (`mobiles` = E.164 without `+`, plus the template variables). A 200 with `type: error` is a failure. Phone numbers are masked in logs; the OTP is never logged.
  - `build_sms_channel(settings)` picks `StubSmsChannel` or `Msg91SmsChannel`; MSG91 without an auth key falls back to the stub with an error log.
  - `SmsOtpDelivery` (`infrastructure/identity/otp_delivery.py`): sends the OTP template, still fills the dev inbox outside production, and turns a provider failure into `ServiceUnavailableError` (503) on `/auth/otp/request`.
- **Wiring**: the API lifespan and the ARQ worker each build one channel per process (it holds an httpx client) and close it on shutdown. `get_otp_delivery` keeps `LoggingOtpDelivery` while `LPG_SMS_PROVIDER=stub`.
- **Swapping provider**: add a class with the same `send` signature and a branch in `build_sms_channel`. The `LPG_SMS_TEMPLATE_*` values become that provider's template IDs (for Gupshup, the DLT template IDs).
- No migration, no API contract change.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `LPG_SMS_PROVIDER` | `stub` | `msg91` to send for real |
| `LPG_MSG91_AUTH_KEY` | empty | MSG91 dashboard → Authkey. Secret |
| `LPG_MSG91_BASE_URL` | `https://control.msg91.com` | |
| `LPG_SMS_REQUEST_TIMEOUT_SECONDS` | `10` | |
| `LPG_SMS_TEMPLATE_LOGIN_OTP` | empty | MSG91 template ID |
| `LPG_SMS_TEMPLATE_DELIVERY_OTP` | empty | MSG91 template ID |
| `LPG_SMS_TEMPLATE_BOOKING_CONFIRMED` | empty | MSG91 template ID |
| `LPG_SMS_TEMPLATE_OUT_FOR_DELIVERY` | empty | MSG91 template ID |
| `LPG_SMS_TEMPLATE_DELIVERY_CONFIRMED` | empty | MSG91 template ID |

Sender ID (header), DLT entity ID and each DLT template ID are entered in the MSG91 dashboard when the MSG91 template is created, not here. A message whose template ID is unset fails and is recorded as failed in the notification log.

## DLT templates to register

Register on a DLT portal (Jio, Airtel, Vi, …) under the principal entity, against one 6-letter sender header, then create a matching MSG91 template for each with the DLT template ID. DLT uses `{#var#}`; MSG91 uses the named placeholders below, which must match exactly. Replace `<Brand>` with the registered brand name. OTP wording assumes the default 5-minute `LPG_OTP_TTL_SECONDS`.

| Key | Content type | DLT text | MSG91 variables |
|---|---|---|---|
| `login_otp` | Service Implicit | `{#var#} is your OTP to sign in to the <Brand> app. It is valid for 5 minutes. Do not share it with anyone.` | `##otp##` |
| `delivery_otp` | Service Implicit | `{#var#} is the OTP to confirm delivery of your <Brand> LPG cylinder. Share it with the delivery person only after you receive the cylinder.` | `##otp##` |
| `booking_confirmed` | Service Implicit | `Your <Brand> LPG order #{#var#} has been confirmed. We will let you know when it is out for delivery.` | `##order_ref##` |
| `out_for_delivery` | Service Implicit | `Your <Brand> LPG order #{#var#} is out for delivery.` | `##order_ref##` |
| `delivery_confirmed` | Service Implicit | `Your <Brand> LPG order #{#var#} has been delivered. Thank you.` | `##order_ref##` |

`order_ref` is the 8-character order reference already used in push and in-app messages.

## Testing

- Unit: channel selection, MSG91 request shape, missing template, non-E.164 number, error body with HTTP 200, HTTP error, network error; `SmsOtpDelivery` template per purpose, dev inbox only outside production, provider failure → 503; `DepartOrderUseCase` sends the delivery OTP and survives an SMS outage.
- Integration: existing OTP flows (`test_auth_flows.py`, order/route smoke tests) with the updated test doubles.
- Live: one real SMS per template once MSG91 + DLT are approved (needs the product owner).
