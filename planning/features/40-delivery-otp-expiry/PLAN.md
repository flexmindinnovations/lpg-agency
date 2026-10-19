# 40 — Delivery code expiring before the driver arrives — Plan

## Problem

Reported 2026-10-19: recording a delivery in the Driver App failed with "The
OTP has expired". The delivery OTP is issued when the driver departs
(`POST /orders/{id}/depart`) but was stored with the 5-minute login TTL
(`otp_ttl_seconds`), so it had expired before almost any driver reached the
customer. There was also no way to send the customer a fresh code.

## Changes

- **Config:** new `delivery_otp_ttl_seconds` (`LPG_DELIVERY_OTP_TTL_SECONDS`),
  default 86400 (one delivery day). The login OTP keeps its 5 minutes.
- **Application:** `OtpStore.issue()` takes an optional `ttl_seconds`;
  `DepartOrderUseCase` uses the delivery TTL. New `ResendDeliveryOtpUseCase`
  (order must be `out_for_delivery`; replaces the earlier code; an SMS failure
  is a 503). `DeliverOrderUseCase` explains an expired code and points the
  driver at "Send a new code".
- **API:** `POST /orders/{id}/delivery-otp` (204; `orders:deliver`, own-order
  check, rate-limited 10 per 10 minutes per IP). OpenAPI regenerated.
- **Testing only (non-production):** delivery codes get their own dev-inbox
  slot for the delivery TTL, read back by `GET /dev/orders/{id}/delivery-otp`.
- **Driver App:** "Send a new code" under the delivery-code field; with
  `SHOW_DEV_OTP` the screen shows the customer's code in the testing banner.
