# 45 — Simpler dispatch (trip sheet) — Tasks

- [x] Map the current dispatch flow and propose the trip sheet (thread reply, 2026-10-19)
- [x] `LoadAndDispatchRouteUseCase` + `POST /routes/{id}/load-and-dispatch`
- [x] Reserve backorders of orders added before the van was loaded
- [x] Trip sheet drawer, trip detail actions, board labels
- [x] Unit, integration and e2e coverage
- [x] ADR-056
- [x] Order page: Send out drawer (replaces Assign + Dispatch) and a progress line (user ask, 2026-10-19)

## Follow-ups (not in scope)

- `order-to-delivery-workflow.spec.ts` reads the delivery OTP from `/dev/otp-inbox/{phone}`, but delivery codes moved to their own inbox key in feature 40, so the spec stops at the Deliver step. It needs the driver-authenticated `/dev/orders/{id}/delivery-otp` instead.
- The Driver App's load manifest shows only what the office loaded; free stock already on the van from an earlier trip isn't listed.
