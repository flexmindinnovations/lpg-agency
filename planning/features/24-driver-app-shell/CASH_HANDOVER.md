# Plan: Driver cash-handover screen

**Phase:** 24 (increment — follows the shell + Stage-D2 regression work)
**Status:** Planned, not started
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

## Stage 1 — Backend: read endpoint + double-declare guard

### 1a. `GET /api/v1/cash-handovers/for-route/{route_id}`

New, in [cash_handover.py](../../../backend/src/lpg/api/v1/routers/cash_handover.py).
`require_permission("cash_handovers:declare")` (or `routes:read`), driver-scoped
exactly like the POST (`route.driver_id != caller's driver → 404`,
indistinguishable from not-found).

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

New use case `GetRouteCashHandoverViewUseCase` in `application/accounting`; new
port method `CashHandoverRepository.get_by_route(route_id) -> CashHandover | None`.

### 1b. Guard the POST

In `DeclareCashHandoverUseCase.execute`, after the route check: if
`get_by_route()` is not None → raise
`ConflictError("Cash handover already declared for this route.")`
(`error_code: "CONFLICT"`). Also require `route.status == "completed"` (BR-32
says "completed route") → `ValidationError` otherwise (**decision 1**).

### 1c. Migration

Unique index `uq_cash_handover_route ON accounting.cash_handover (route_id)` —
DB-level backstop for 1b.

### 1d. Tests

- unit: `get_by_route` None → declare succeeds; row present → `ConflictError`.
- integration smoke (seeded e2e driver): completed route + one cash POD →
  `GET .../for-route` shows `expected_amount`, `handover: null` → `POST` → 201 →
  `GET` now shows the handover → second `POST` → 409. Another driver's
  `GET`/`POST` → 404.

Gate: `uv run pytest`, `ruff check src tests`, `mypy src`, `lint-imports`.

---

## Stage 2 — `packages/api_client`

- **`cash_handover_api.dart`** (new) — `CashHandoverApi(this._dio)`:
  - `Future<Result<RouteCashHandover>> getForRoute(String routeId)`
  - `Future<Result<CashHandover>> declare({required String routeId, required String driverId, required double actualAmount})`
- **`models/cash_handover_models.dart`** (new) — `CashHandover` (mirrors
  `CashHandoverResponse`: handoverNumber, expectedAmount, actualAmount,
  shortfall, declaredAt) + `RouteCashHandover` (the view: routeStatus,
  routeDate, expectedAmount, cashStopCount, handover?). Decimals arrive as JSON
  strings → parse to `double`.
- barrel exports in `api_client.dart` + `models/models.dart`.
- `cash_handover_api_test.dart` — request paths, 409 mapping, null-handover parse.

---

## Stage 3 — `driver_app`: screen, providers, route

- **`api_provider.dart`** —
  `cashHandoverApiProvider = Provider((ref) => CashHandoverApi(ref.watch(apiClientProvider).dio))`.
- **`features/cash_handover/data/cash_handover_provider.dart`** (new):
  - `routeCashHandoverProvider = FutureProvider.autoDispose.family<RouteCashHandover, String>((ref, routeId) => …getForRoute)`.
  - `pendingCashHandoverProvider = FutureProvider.autoDispose<RouteCashHandover?>`
    — reads `routeHistoryProvider`, takes the most recent `completed` route,
    fetches its view, returns it iff `handover == null`. Drives the Today-tab
    nudge.
- **`features/cash_handover/presentation/cash_handover_screen.dart`** (new) —
  `ConsumerStatefulWidget`, `CashHandoverScreen({required this.routeId})`.
  Watches `routeCashHandoverProvider(routeId)`:
  - **loading / error** → `LpgLoadingIndicator` / `LpgEmptyState` + Retry
    (match `stop_detail_screen`).
  - **`handover != null`** → *receipt* `LpgCard`: handover number,
    Expected ₹X, Handed over ₹Y, **Shortfall ₹Z** (danger badge) or "Matched" /
    "Over by ₹Z", declared date. Read-only. Copy: "This route's cash has been
    reconciled."
  - **`handover == null`** →
    - header: route date + "N cash deliveries"
    - **Expected cash: ₹X** — large, read-only, the number to count against
    - `LpgTextField` "Amount you're handing over (₹)",
      `keyboardType: numberWithOptions(decimal: true)`, live delta line as they
      type ("Matches expected" / "Short by ₹Y" / "Over by ₹Z")
    - `LpgButton "Declare handover"` → confirm dialog ("Hand over ₹Y for the
      {date} route? This can't be undone.") → `declare(…)` → on success
      `ref.invalidate` both providers, snackbar, stay on screen (re-renders as
      the receipt).
    - 409 from a race → friendly "Already declared" + refetch.
  - `driverId` for the POST comes from `RouteCashHandover.driverId` in the view
    response (preferred — no dependency on `driverProfileProvider`).
- **`router.dart`** — top-level route above the shell (same tier as
  `/stops/:orderId`):
  ```dart
  GoRoute(
    path: '/routes/:routeId/cash-handover',
    name: 'cashHandover',
    builder: (c, s) => CashHandoverScreen(routeId: s.pathParameters['routeId']!),
  ),
  ```

---

## Stage 4 — Entry points

- **Today tab** ([today_screen.dart](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/today_screen.dart))
  — watch `pendingCashHandoverProvider`; when non-null, render a card (below the
  route section / empty state): *"Cash reconciliation pending — declare the cash
  for your {date} route"* →
  `context.pushNamed('cashHandover', pathParameters: {'routeId': …})`. Main
  discoverable path.
- **Deliveries tab → "Past routes"**
  ([deliveries_screen.dart](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/deliveries_screen.dart))
  — make `_HistoryRow` tappable for `completed` routes → the same route. Add a
  trailing chip: "Cash pending" (warning) / "Cash ✓" (success). Requires the row
  to know handover status — prefer widening `routeHistoryProvider` (or a batch
  `GET /cash-handovers?route_ids=`) over an N+1 of per-row GETs.
- *(Not doing:* a Profile "Cash handovers" history list — overkill for v1.)*

---

## Stage 5 — Tests + emulator verification

- `cash_handover_screen_test.dart` — (a) pending view → enter amount → delta
  line → confirm → declare called → receipt renders; (b) already-declared →
  receipt, no input; (c) `expected = 0` → still declarable; (d) 409 → recovers.
- `deliveries_screen_test.dart` / `today_screen_test.dart` — new entry-point
  rendering with overridden providers.
- **Emulator** (`emulator-5554`, seeded e2e driver): deliver a cash order →
  complete the route → Today shows the nudge → open screen → expected matches
  the POD amount → declare short by ₹50 → receipt shows ₹50 shortfall → reopen
  from Deliveries → read-only receipt. Screenshot; note in
  [STATUS.md](./STATUS.md).

Gate: `driver_app` + `api_client` `flutter test` + `flutter analyze` clean.

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
