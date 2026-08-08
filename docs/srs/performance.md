# Performance Requirements

## 1. Source Coverage
The blueprint explicitly names "Load Testing" as part of Phase 7 (Testing) but did not originally define specific numeric targets. **These targets are now CONFIRMED per `business/decisions.md` D-34** and are binding SLAs, not proposals.

## 2. Response Time & Scalability Targets — CONFIRMED (D-34)
| Metric | Confirmed Target |
|---|---|
| API response (average) | < 300ms |
| Search | < 1 second |
| Dashboard load | < 2 seconds |
| Report generation | < 10 seconds |
| Concurrent users | 500+ **per tenant** |
| Scaling model | Horizontal scaling enabled |

The following finer-grained targets from the original proposal remain useful supplementary guidance (not yet explicitly re-confirmed at this granularity, but consistent with the confirmed averages above) and should be validated during performance test design:

| Interaction | Suggested Target |
|---|---|
| Dashboard navigation (subsequent, post-load) | < 500ms |
| Customer App booking submission | < 1s |
| Driver App delivery confirmation sync (online) | < 2s |
| Real-time order status update propagation | < 5s |

## 3. Scalability Targets — CONFIRMED (D-34, D-01)
- **500+ concurrent Dashboard/API users per tenant** is now the confirmed baseline, directly tied to the confirmed multi-tenant architecture (D-01) — the system must scale this per-tenant target across an arbitrary number of tenants via horizontal scaling.
- Customer-base scale (hundreds to tens of thousands per agency) remains consistent with the platform's multi-tenant SaaS ambition.

## 4. Frontend Performance Practices (Explicit in Extended Instructions)
- Lazy loading and code splitting for Dashboard modules.
- Image optimization (e.g., KYC document thumbnails, delivery photo proofs).
- Virtual scrolling for large data tables (customer lists, order lists, transaction histories).
- Caching of relatively static reference data (cylinder types, pricing tables).
- Optimistic UI updates for actions like order status changes, with rollback on failure.
- Background synchronization for the Driver App, particularly to support offline-capture-and-sync (ties to assumption A-18).

## 5. Backend Performance Practices
- Reporting queries (Daily Sales, Cylinder Movement, Reconciliation) should not run against live transactional tables at scale without safeguards — consider precomputed/materialized aggregates as data volume grows (design-level guidance, not a hard requirement in this document).
- Cylinder Ledger and Inventory transactions require per-customer/per-location locking or equivalent concurrency control to avoid race conditions under concurrent load (ties to `workflows/cylinder-ledger.md` §8, `workflows/inventory-flow.md` §6).

## 6. Load & Stress Testing
- Load testing shall be performed prior to production release (explicit, Phase 7).
- Recommended scope: simulate peak-hour booking traffic, simulate a full day's worth of delivery-confirmation events across a full fleet, simulate concurrent report generation by multiple staff.

## 7. Mobile Network Conditions
- The Driver App, given field usage in potentially low-connectivity areas, should be tested under degraded network conditions (2G/3G, intermittent connectivity), not just ideal Wi-Fi/4G conditions — inferred requirement.

## 8. Open Items
**Resolved.** Numeric SLAs and concurrency targets are now confirmed (D-34, §2 above). Remaining work is translating these tenant-level SLAs into concrete load-test scenarios during the design/test-planning phase — an implementation detail, not an open business question.
