# Capacity and concurrency review (2026-11-01)

Scope: what the production stack is sized for, how concurrent requests are protected, and how order and payment races behave. Based on the code and deploy config at `origin/main` (a17c8bc), plus race probes and a load test on a local copy of the stack. Review only; the one change made is a small payment fix (see section 5).

## 1. Server configuration (from `infrastructure/deploy` and `backend/gunicorn.conf.py`)

| Item | Setting |
|---|---|
| Host | One DigitalOcean droplet: 1 vCPU, 2 GB RAM, 2 GB swap, Ubuntu 24.04 (DEPLOY.md). Everything runs on it. |
| Containers | postgres 17, redis 7, backend (gunicorn), worker (arq jobs and cron), web (Caddy). Only Caddy publishes ports. |
| API processes | gunicorn with `UvicornWorker`, `WEB_CONCURRENCY=2` in compose. `worker_connections=50000` and the "100,000 concurrent users" comment in `gunicorn.conf.py` are aspirational; nothing is sized or tested for that. Timeout 120 s, keepalive 120 s. |
| DB pool | SQLAlchemy async: 10 pooled + 5 overflow per process, 30 s pool timeout. Two API workers plus the arq worker is up to 45 connections. |
| Postgres | `max_connections=60`, `shared_buffers=128MB`, `effective_cache_size=512MB`. About 15 connections of headroom. Raising `WEB_CONCURRENCY` to 4 would exceed 60 and needs the pool or `max_connections` changed first. |
| Redis | 128 MB, `noeviction`, AOF on. Holds idempotency keys, OTPs, rate-limit counters, realtime pub/sub. |
| Caddy | gzip/zstd, security headers, 12 MB request body cap, no explicit timeouts, no connection or rate limits, no access log. |
| Rate limits | Only on auth: login 10/min/IP, OTP request 30/h/IP plus per phone, OTP verify 30/10 min/IP plus per phone, refresh 60/min, password flows. Nothing on ordinary API calls or order creation. The limiter fails open if Redis is down. |
| WebSocket `/api/v1/ws` | In-process `ConnectionManager` per worker, one Redis subscriber per worker, ping interval, auth frame timeout. No cap on connection count. Capacity is bounded by RAM, file descriptors and the single CPU. Not load-tested. |

## 2. How concurrency is controlled

- Default Postgres isolation (READ COMMITTED); no SERIALIZABLE anywhere. Each request is one transaction (unit of work), tenant id set per transaction for row-level security.
- `version` columns exist on most tables and are incremented on update, but **no code compares them** (no `version_id_col`, no `WHERE version = ?`). There is no optimistic locking today. The comment in `auto_assignment_jobs.py` saying there is no `with_for_update` is out of date; it is used in three places (below).
- Advisory locks (transaction scoped, released on commit or rollback): per-branch booking lock (`lock_branch_for_booking`), crew lock per driver and vehicle when opening a trip (`lock_crew`, fixed order so no deadlocks), per-driver lock in the auto-assignment job.
- Row locks (`FOR UPDATE`): online payments, reconciliation decision. Added by this review: invoices when a payment is applied.
- Unique constraints: `(tenant, order_number)`, `(tenant, invoice_number)`, one invoice per order, one active route stop per order (partial index), one pending cancellation per order, one cash handover per route, unique payment link id, unique inventory balance per location/type/status. Database errors map to clean 409s (`translate_database_error`, including 40001 and 40P01).
- Idempotency: `Idempotency-Key` required on `POST /orders` and also used on assign, depart, deliver, load-and-dispatch, cash handover and other driver actions. Redis `SET NX`, request fingerprint, concurrent duplicates wait and replay the stored result.
- Order numbers: `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` on a per-tenant sequence row (row lock until commit).
- State machines: domain aggregates reject illegal transitions, but only against the state they loaded (see weak spots).

## 3. Race scenarios

"Tested" means I ran parallel requests against a real Postgres and Redis (probe script kept in the scratchpad, not committed), or the repo already has a test.

| Scenario | Result | Verdict |
|---|---|---|
| Two customers order the last cylinders | Branch advisory lock plus stock-minus-open-demand check. 4 parallel bookings of 150 from 200: exactly one 201, three 409. Existing test in `test_order_endpoints_smoke.py`. | Solid. It serialises all bookings in a branch; fine at this scale. |
| Double-submitted order, same key | 6 parallel identical requests: six 201 replies, one order, same id. | Solid. |
| Double-submitted order, new key each tap | 5 parallel requests with different keys create 5 orders. | By design, so the apps must keep one key per attempt (the Dart client does take a caller-supplied key; I did not audit every call site). |
| Order number generation | 6 concurrent orders: 6 distinct numbers; unique index as backstop; existing sequence test. | Solid. |
| Two dispatchers assign one order (new trip) | 4 parallel assigns: one 200, three 409 `DRIVER_ALREADY_ON_TRIP`, one stop, stock reserved once. Two different drivers (not run): by the code, the partial unique index on route stops makes the loser fail with a 409. | Solid. |
| Several orders assigned to the same route at once | 8 parallel `assign-order` calls on one trip: all 200, 9 stops, but the van's filled balance dropped by 6 instead of 27, in 3 of 3 runs. Reservations were lost. | **Weak: stock drift.** |
| Cancel versus assign | Run 12 times in parallel: 2 runs ended with both calls returning 200 and an inconsistent result (history shows both `cancelled` and `assigned`, final status `assigned`, so a cancel the customer was told succeeded is lost). | **Weak: lost update.** |
| Repeated confirm | 4 parallel confirms: all 200, 4 `confirmed` history rows, so duplicate events and notifications. | Weak but low impact. |
| Repeated cancel | 3 parallel cancels: all 200, stock restored once. | Acceptable by luck; same pattern as above. |
| Double delivery | 4 parallel deliver calls with different keys and the same OTP: one 200, three 410, one proof-of-delivery row, stock moved once. | Solid in practice. The OTP check is read then delete in Redis (not atomic), so a very tight window remains. |
| Double payment (staff or cash recorded twice) | 4 parallel full payments on one invoice of 1,995.00: four 201 replies, four rows, 7,980.00 recorded. | **Defect, fixed in the PR below.** |
| Webhook versus staff payment | Gateway side is solid: payment row locked, `applied_payment_id` makes it idempotent, webhook and refresh cannot double-apply. But applying it to the invoice used the same unlocked invoice read, so it could race with a staff payment. | Fixed by the same PR. |
| Webhook versus driver collecting cash at the door | Delivery settlement subtracts captured online payments; a payment landing during the delivery request is not re-checked. | Narrow window; unmitigated, low priority. |
| Cancellation versus dispatch of a loaded van | Same unlocked order read as above. | Weak (same fix as cancel versus assign). |
| Stock and inventory movements in general | Each movement loads the location, changes it in memory, then writes the absolute balance back with no lock and no version check. Concurrent movements on one location (two assigns on one van, goods receipt during a transfer) can overwrite each other. Source of the drift above. | **Weak.** |
| OTP verification attempts | Max 5 wrong codes then the code is burned (PR #100), plus per-IP and per-phone throttles. By reading the code (not run), a parallel burst can test a few extra codes before the counter lands, because get, compare and incr are separate Redis calls. | Good; small hardening possible with an atomic script. |

## 4. Capacity estimate (estimate only)

Method: the production container settings were copied (2 gunicorn workers, default pool, Postgres `max_connections=60`), and gunicorn, Postgres and Redis were all pinned to **one CPU core** to mimic a 1 vCPU droplet. Load generator on separate cores. Mix: 70% order list, 15% orderable-cylinder list (customer), 10% create order, 5% `/auth/me`. Zero think time, so every virtual user is hammering.

| Concurrent in-flight users | Throughput | List p50 / p95 | Create p50 / p95 | Errors |
|---|---|---|---|---|
| 10 | 67 req/s | 50 / 273 ms | 431 / 655 ms | 0 |
| 50 | 50 req/s | 722 / 1,637 ms | 2.2 / 4.4 s | 0 |
| 100 | 58 req/s | 1.2 / 2.6 s | 4.3 / 7.8 s | 0 |
| 300 | 53 req/s | 4.5 / 5.9 s | 14 / 18 s | 0 |

Reading it: the stack tops out around **50 to 65 requests per second** on one core, then queues. It degrades gracefully (no errors, no pool exhaustion even at 300 in flight) but latency grows linearly with load. Order creation is the heaviest call (about 10 requests of CPU each).

A real app user makes roughly one request every 5 to 10 seconds. So the sustained ceiling is on the order of **300 to 500 concurrently active users**, but comfortable response times (page loads under about 1 s, order creation under about 1 s) hold only up to roughly **100 to 150 concurrently active users** (about 10 to 25 requests in flight). That is plenty for a handful of agencies (each with maybe 5 to 20 staff and drivers online, customers mostly idle) and not enough for thousands of simultaneous customers. Not measured: Caddy and TLS overhead, WebSocket fan-out, memory (OCR/ONNX in the backend is the likely first problem on 2 GB), a DigitalOcean shared vCPU (may be slower than the test core), and a database that has run for months. Treat the numbers as an order of magnitude.

## 5. What changed in this review

One small fix, open as a PR: recording a payment now locks the invoice row (`SELECT ... FOR UPDATE`), and so does applying a gateway payment to an invoice, with a regression test (4 parallel full payments: one succeeds, the rest are refused; fails without the fix). No schema change.

## 6. Recommended priorities (not done; need your go-ahead)

1. **Lock the inventory location when it is loaded for a movement** (a `FOR UPDATE` on the location row, taking locks in sorted id order when two are involved). Fixes the lost reservations and stock drift. Small diff, but it touches every inventory path, so it needs the full integration suite and a deadlock check.
2. **Lock the order row on every state change** (assign, cancel, confirm, deliver, depart), or add a real version check (`UPDATE ... WHERE version = :v`, 409 on mismatch). Fixes cancel versus assign and duplicate confirms. The version column is already there, so optimistic locking is the cleaner route.
3. Add concurrency tests for both (the probes in this review can be turned into tests).
4. Make OTP verify atomic with a small Redis script.
5. Capacity: add a general per-user and per-IP rate limit on write endpoints, move to 2 vCPU / 4 GB before onboarding many agencies, and keep Postgres connections under `max_connections` if workers are raised.
6. Correct the stale comments in `gunicorn.conf.py` (100,000 users) and `auto_assignment_jobs.py` (no `with_for_update`).
