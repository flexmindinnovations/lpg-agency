# Plan: Driver cash-handover screen

**Phase:** 24 (increment — follows the shell + Stage-D2 regression work)
**Status:** ✅ Complete — all 5 stages done 2026-09-02
**Drafted:** 2026-09-02

---

## Context

Drivers collect cash on delivery (`payment_method: 'cash'` PODs). At end of route
they hand that cash to the agency and declare the amount. The backend has
`POST /api/v1/cash-handovers` and the `driver` role holds
`cash_handovers:declare`, but there is **no UI** — the money side of the
delivery workflow just ends.

**Domain shape** ([cash_handover.py](../../../backend/src/lpg/domain/accounting/cash_handover.py),
[use_cases.py:225](../../../backend/src/lpg/application/accounting/use_cases.py)):

- One `CashHandover` per completed route. `expected_amount` =
  `SUM(pod.amount_collected)` for cash PODs on that route — computed
  **server-side, never trusted from the client**.
- `shortfall = max(expected − actual, 0)`. A `CashShortfallDeclared` event
  fires when `actual < expected`.
- Row is INSERT-only (UPDATE/DELETE revoked) — immutable once declared.
- Route lifecycle `planned → loaded → in_progress → completed → reconciled`;
  `in_progress → completed` happens automatically when the last stop finishes
  (confirmed in the Stage-D2 regression run).

## Blocking gaps in the backend

1. **No read path.** `expected_amount` appears only in the POST 201 response.
   The driver can't see the target before declaring, and can't see what they
   already declared. Need a GET.
2. **No idempotency.** No unique constraint on `route_id`, no check in the use
   case — a driver can declare the same route repeatedly, each a new row.
   ([migration c039189dfbdc](../../../backend/migrations/versions/c039189dfbdc_create_cash_handover_table.py)
   has plain indexes on `route_id`, not UNIQUE.)
3. **`CashShortfallDeclared` has no consumer** — the "office gets alerted on a
   shortfall" path isn't wired. *(Out of scope for the screen; flagged as a
   follow-up.)*
4. **Timing.** `get_active_route_for_driver` only returns
   `planned/loaded/in_progress` — so the moment the route completes and the
   handover becomes relevant, it drops out of `activeRouteProvider` and all
   order visibility. The entry point must come from route *history*, not the
   active route.

---

## Stage 1 — Backend: read endpoint + double-declare guard  ✅ DONE 2026-09-02

Commit: *(pending)*. 757 unit + 7 cash-handover / 4 driver integration tests
pass; ruff / mypy / lint-imports clean. Verified live against the dev DB with
the seeded e2e driver (declare → 201 `CSH000003` shortfall computed
server-side → re-GET shows the handover → second declare → 409).

**Deviation from the draft:** the GET is **not** driver-only. A `driver`
principal is scoped to their own routes; dispatch staff (who also hold
`cash_handovers:declare`, per `c039189dfbdc`) can read any route in their
tenant — the same "or dispatcher/manager on their behalf" split the POST
already has. RLS on `route_repository.get_by_id` keeps it tenant-scoped.

### 1a. `GET /api/v1/cash-handovers/for-route/{route_id}`  ✅

New, in [cash_handover.py](../../../backend/src/lpg/api/v1/routers/cash_handover.py).
`require_permission("cash_handovers:declare")`. Driver principal → scoped to
their routes; staff → any in-tenant route. `404` for a route the caller
can't see (indistinguishable from not-found).

Response — one call, everything the screen needs:

```python
class RouteCashHandoverView(BaseModel):
    route_id: uuid.UUID
    driver_id: uuid.UUID
    route_status: str          # so the screen can gate on "completed"
    route_date: date | None
    expected_amount: Decimal   # from get_expected_cash_for_route()
    cash_stop_count: int       # # of cash PODs, for "3 cash deliveries"
    handover: CashHandoverResponse | None   # null = not yet declared
```

Use case `GetRouteCashHandoverViewUseCase` + `RouteCashHandoverView` dataclass
in `application/accounting/use_cases.py`; port methods
`CashHandoverRepository.get_by_route()` and `.count_cash_stops_for_route()`
(the latter feeds `cash_stop_count` — "you should have ₹X from N cash
deliveries"). Schema `RouteCashHandoverResponse` in `schemas/cash_handover.py`.

### 1b. Guard the POST  ✅

In `DeclareCashHandoverUseCase.execute`, after the route check:
`get_by_route()` not None → `ConflictError` (409 `CONFLICT`); then
`route.status != "completed"` → `ValidationError` (422).

### 1c. Migration  ✅

[`a7f1c93e6b20_cash_handover_route_unique.py`](../../../backend/migrations/versions/a7f1c93e6b20_cash_handover_route_unique.py)
— collapses any pre-existing duplicates (keep earliest per route), then
`ADD CONSTRAINT uq_cash_handover_route UNIQUE (route_id)`. The dev DB *had*
a dupe (the bug); test DB migrated clean.

### 1d. Tests  ✅

- unit (`test_accounting_use_cases.py`): declare → `ConflictError` when a
  handover exists; `ValidationError` when route not `completed`; new
  `TestGetRouteCashHandoverViewUseCase` (undeclared → expected + null handover;
  declared → handover included; other driver's route → `NotFoundError`).
  `_make_route` / `mock_cash_handover_repo` fixtures updated.
- integration (`test_cash_handover_endpoints_smoke.py`): `for-route` view
  before/after declare (expected `750.00`, `cash_stop_count 1`, then handover
  populated); second declare → 409 `CONFLICT`; declare while `in_progress`
  → 422. `_seed_route_with_cash_delivery` gained a `route_status` param.

Gate: `pytest tests/unit` (757 pass), cash-handover + driver integration
(11 pass), `ruff check src tests`, `mypy src`, `lint-imports` — all clean.

---

## Stage 2 — `packages/api_client`  ✅ DONE 2026-09-02

Commit: *(pending)*. api_client 53 tests pass (+5), analyze clean;
driver_app 37 pass, analyze clean.

- **`cash_handover_api.dart`** — `CashHandoverApi(this._dio)`:
  - `getForRoute(String routeId) -> Result<RouteCashHandover>`
  - `declare({routeId, driverId, actualAmount}) -> Result<CashHandover>` —
    sends `actual_amount` as `toStringAsFixed(2)` (avoids `Decimal` float
    drift).
- **`models/cash_handover_models.dart`** — `CashHandover` (id,
  handoverNumber?, driverId, routeId, expectedAmount, actualAmount,
  shortfall, declaredBy, declaredAt; `surplus` getter) + `RouteCashHandover`
  (routeStatus, routeDate, expectedAmount, cashStopCount, handover?;
  `isDeclared` / `isPending` getters for the Stage-4 entry points).
  Decimals via `asDouble` (the package's `decimal_json.dart` helper).
- barrel exports added to `api_client.dart` + `models/models.dart`.
- `cash_handover_api_test.dart` — 5 tests: expected-only parse, populated
  handover, 404 → failure, POST body shape + fixed-2 amount, 409 → failure
  with `errorCode == "CONFLICT"`.

---

## Stage 3 — `driver_app`: screen, providers, route  ✅ DONE 2026-09-02

Commit: *(pending)*. driver_app 42 tests pass (+5), analyze clean. Live
emulator walkthrough deferred to Stage 5 (needs the entry points).

- **`api_provider.dart`** — `cashHandoverApiProvider`.
- **`features/cash_handover/data/cash_handover_provider.dart`**:
  - `routeCashHandoverProvider` (`autoDispose.family<RouteCashHandover, String>`).
  - `pendingCashHandoverProvider` (`autoDispose<RouteCashHandover?>`) — walks
    `routeHistoryProvider` (already newest-first) for the latest `completed`
    route, fetches its view, returns it only when `isPending`. A load failure
    → `null` (no nudge).
- **`features/cash_handover/presentation/cash_handover_screen.dart`** —
  `ConsumerStatefulWidget`, watches `routeCashHandoverProvider(routeId)`:
  - loading / error → `LpgLoadingIndicator` / `LpgEmptyState` + Retry.
  - `handover != null` → `_Receipt`: handover number + `SHORT`/`OVER`/
    `RECONCILED` badge, Expected / Handed over / Shortfall|Over rows,
    declared date, "This route's cash has been reconciled."
  - `routeStatus != 'completed'` → "still in progress" empty state, no form.
  - else → `_DeclareForm`: `_formatDate` header + "from N cash deliveries",
    big **Expected cash ₹X**, `LpgTextField` (decimal keyboard) with a live
    `_DeltaLine` ("Matches" / "Short by ₹Y" / "Over by ₹Z"), `LpgButton
    "Declare handover"` → `AlertDialog` confirm → `declare(…)` (driverId from
    the view response). On success: invalidate `routeCashHandoverProvider` +
    `pendingCashHandoverProvider` + `routeHistoryProvider`, snackbar, screen
    re-renders as the receipt. 409 → "already been reconciled" + refetch.
- **`router.dart`** — `GoRoute(path: '/routes/:routeId/cash-handover',
  name: 'cashHandover', …)` top-level, right after `/stops/:orderId`.
- **`cash_handover_screen_test.dart`** — 5 tests: expected-amount + declare
  action; live delta line (short / matches / over); in-progress → no form;
  declared → receipt (badge, shortfall row, no field); full declare flow
  (stateful fake adapter: POST body `actual_amount: '900.00'` → screen flips
  to the receipt).

---

## Stage 4 — Entry points  ✅ DONE 2026-09-02

- **Today tab** ([today_screen.dart](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/today_screen.dart))
  — `ref.watch(pendingCashHandoverProvider).value`; when non-null, a
  `_PendingCashCard` renders above the route section (present whether or not
  there's an active route now): "Cash reconciliation pending — Declare ₹X from
  your {date} route" → `pushNamed('cashHandover')`.
- **Deliveries → "Past routes"**
  ([deliveries_screen.dart](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/deliveries_screen.dart))
  — `_HistoryRow` gained `onTap` (set for `completed` routes →
  `pushNamed('cashHandover')`) and a `cashPending` flag → a `CASH PENDING`
  warning badge. `cashPending` is driven off the **same
  `pendingCashHandoverProvider`** (matches its `routeId`) — so it flags only
  the latest completed route, no per-row N+1. Older completed routes are
  still tappable to review their receipt.
- *(Not done:* per-row "declared/pending" chip for every past route — needs a
  batch endpoint or a widened list response; the single-latest flag covers
  the actionable case.)*
- **Tests**: `today_screen_test.dart` +1 (nudge renders for a pending view),
  `deliveries_screen_test.dart` +1 (`CASH PENDING` flags the matching row);
  both `_screen` helpers now override `pendingCashHandoverProvider`.

---

## Stage 5 — Emulator verification  ✅ DONE 2026-09-02

`emulator-5554`, seeded e2e driver, live backend. Full walkthrough:

1. **Today** shows "Cash reconciliation pending — Declare ₹1811.00 from your
   2026-09-01 route" (route `d9cfd7b3`, from `GET .../for-route`).
2. Tap → **CashHandoverScreen**: "Expected cash ₹1811.00 / from 2 cash
   deliveries", amount field.
3. Type `1800` → delta line "Short by ₹11.00" (red).
4. "Declare handover" → confirm dialog ("Hand over ₹1800.00 for the
   2026-09-01 route? This cannot be undone.") → Confirm.
5. Screen flips to the **receipt**: `CSH000004`, `SHORT` badge, Expected
   ₹1811.00 / Handed over ₹1800.00 / **Shortfall ₹11.00**, "Declared
   2026-09-02". Snackbar "Cash handover recorded."
6. Back to **Today** → nudge is **gone** (`pendingCashHandoverProvider`
   invalidated).
7. **Deliveries → Past routes** → tap the 2026-09-01 completed row → the
   same receipt (provider cache reused, instant).

Backend 409 double-declare guard + `for-route` 404 scoping were verified
live in Stage 1.

## Test totals

- `packages/api_client`: 53 (+5 in Stage 2)
- `apps/driver_app`: 44 (+5 Stage 3, +2 Stage 4)
- backend: 757 unit + 7 cash-handover / 4 driver integration
- `flutter analyze` clean for api_client + driver_app; ruff / mypy /
  lint-imports clean for backend.

## Known follow-ups (not blocking)

- Today nudge subtitle truncates the trailing " route" on narrow screens —
  cosmetic.
- No per-past-route cash chip beyond the latest — needs a batch read.

## Post-completion additions

- **`CashShortfallDeclared` → office notification** (2026-09-02) —
  `_on_cash_shortfall_declared` in `notification_handlers.py` enqueues a
  `cash_shortfall_staff` job; `notification_jobs.py` resolves the tenant's
  ops team (`agency_admin` / `manager` / `dispatcher`) and sends an in-app
  notification + email ("Cash shortfall of ₹X on route #Y: expected ₹A,
  driver handed over ₹B", `reference_type: cash_handover`). No push (staff
  use the dashboard). Fires only on a real shortfall. Verified live: a
  ₹55.50 shortfall on the seeded route produced 3 in-app rows + 3 email
  logs. Tests: `test_infrastructure_notification_handlers.py` +1,
  `test_infrastructure_notification_jobs.py` +2.

---

## Open questions / decisions

| # | Question | Recommendation |
|---|---|---|
| 1 | Gate declaration on `route.status == 'completed'`? | **Yes** — BR-32 says "completed route", and declaring mid-route gives a wrong `expected`. Screen shows "Route still in progress" until then. |
| 2 | New feature dir `25-driver-cash-handover`, or fold into 24? | **Folded into 24** (this file). It's an increment, not a phase. |
| 3 | Wire a `CashShortfallDeclared` consumer (notify the office)? | Out of scope here; separate small backend task. |
| 4 | Per-order cash breakdown on the screen? | v1: just the total `expected_amount`. Breakdown is a nice-to-have. |

## Risks / notes

- **Backend-first** — Stages 2–4 are blocked on Stage 1. Rough size: ~1 day
  backend, ~1–1.5 days mobile.
- `Decimal` ↔ `double` — parse JSON decimal strings carefully; compare with a
  cent tolerance in the delta line; send `actual_amount` as a string to avoid
  float drift.
- Entry-point discoverability — the route is gone from `activeRouteProvider` by
  the time this matters, so the Today nudge (via history) is essential.
- Deliveries chip needs handover status per past route — widen
  `routeHistoryProvider` or add a batch endpoint rather than N+1 GETs.
- No money-formatting util in the codebase — follow the existing
  `'₹${x.toStringAsFixed(2)}'` idiom (as in `stop_detail_screen`).
