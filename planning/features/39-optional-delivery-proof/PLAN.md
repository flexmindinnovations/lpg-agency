# 39 — Optional delivery signature and photo — Plan

## Requirement

Product owner, 2026-10-19: when a driver records a delivery in the Driver App,
the customer's signature and the delivery photo must no longer be mandatory.

## Business rule change

BR-08 / BR-23 and FR-DM-06 are amended: the delivery OTP and the GPS stamp
still gate `out_for_delivery → delivered`; signature and photo are captured
when available but are optional. Payment method and amount stay mandatory.

## Changes

- **Database:** `orders.proof_of_delivery.signature_blob_ref` and
  `photo_blob_ref` become nullable (migration `b7e1d3f5a2c9`).
- **API:** `ProofOfDeliverySubmission.signature_blob_ref` / `photo_blob_ref`
  are optional (a supplied value must still be non-empty);
  `ProofOfDeliveryResponse` returns them as nullable. OpenAPI and the
  generated dashboard client regenerated.
- **Application:** `DeliverOrderCommand` takes `str | None`; the use case
  rejects only a supplied-but-blank reference.
- **Driver App:** the record-delivery screen no longer blocks submit; the
  section headings say "(optional)". `DeliveryMutations` uploads only what was
  captured, online and offline (the queued op lists only captured media, and
  `SyncCoordinator` already handles any number of media entries).
- **Dashboard:** unchanged — staff delivery from Order Detail still asks for
  both (not part of this request).
