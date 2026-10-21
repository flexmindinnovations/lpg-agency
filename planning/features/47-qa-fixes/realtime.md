# QA fixes — realtime and notifications

Owner thread: realtime. Branch `qa-fix/realtime`. No migrations. No REST schema change, so the client was not regenerated. The WebSocket protocol changed; see "Protocol" below.

## DO-27 / CA-05: in-app notifications were never created

**Root cause.** Only the arq worker wrote in-app rows. The QA stack ran no worker, and several alert types did not exist at all. Staff recipients were looked up as employee → phone → identity, which matched nobody on the seed data.

**What changed**

- Domain events:
  - `backend/src/lpg/domain/order/order.py`: new `CancellationRequested` event.
  - `application/order/use_cases.py`: the pending-approval cancel now saves the order, so the event is dispatched.
  - `domain/complaint/complaint.py`: new `ComplaintAssigned` event.
- `infrastructure/notification/catalog.py` (new): one spec per notification type. Each spec holds the title and body (order number, customer name, ₹ amounts), the audience, the permission and the channels.
- `infrastructure/notification/recipients.py` (new): resolves the recipients.
  - Staff are chosen by permission and branch: branch-scoped users match their own branch, and users with no branch see every branch.
  - The actor is excluded.
  - Customers, drivers and assignees are resolved under the tenant's RLS session.
- `infrastructure/notification/delivery.py` (new):
  - `InAppFirstNotifier` writes the in-app rows in the API process right after the business commit. It never raises, because a post-commit failure would otherwise turn a successful action into a 500.
  - It then queues email, SMS and push for the worker with `in_app_delivered`.
- `infrastructure/jobs/notification_jobs.py`: now a thin worker job for the external channels only.
- `infrastructure/events/notification_handlers.py`: rewritten, with a handler for every alert in the brief:
  - staff: new order
  - manager/admin: cancellation request
  - staff and assignee: complaint raised or assigned
  - staff and customer: failed delivery
  - customer: confirmed, out for delivery, delivered and cancelled
  - driver: route dispatched, resequenced, cancelled, and stop cancelled
  - customer and accountant: payment received
- `infrastructure/events/low_stock_handlers.py` (new): runs a live low-stock check when a van is loaded.
- `jobs/inventory_jobs.py`: the per-tenant check function is reused for it.
- `persistence/repositories/notification.py`: new `SqlAlchemyNotificationRecipientRepository`.
- `api/app.py` and `jobs/worker.py`: wiring.

**Verified**

- Unit tests: `test_infrastructure_notification_catalog.py` and `test_infrastructure_notification_handlers.py`.
- Integration test `test_in_app_notifications_integration.py`, run on `lpg_test_realtime`. It checks:
  - RBAC
  - branch scope
  - actor exclusion
  - customer delivery
  - that an assignee from another tenant is rejected
  - that RLS hides another tenant's order

## Live delivery and read sync (brief item 2)

**Backend**

- `application/notification/use_cases.py`: mark-read and mark-all-read publish `notification.read` and `notification.read_all` on the user's channel after commit, on a best-effort basis.
- `realtime_handlers.py`: `notification.new` now carries `created_at`.

**Dashboard (`libs/shared/data-access`, `libs/notification/*`)**

- The bell updates its count live, shows a toast for new items and caps the badge at 99+.
- The drawer and the inbox page:
  - group items by day
  - mark unread items
  - have empty and loading states
  - offer mark-all-read
  - follow deep links: order, complaint (`?complaint=`), dispatch, invoices, inventory, compliance and price lists
  - reload live

**Mobile**

- The shell streams in both apps now also carry read events and a reconnect marker:
  - customer: `subscribeToNotificationChanges`
  - driver: `subscribeToDriverUpdates`, which adds route events

**Verified**

- Jest specs pass for:
  - `shared-data-access`, including the websocket and notification services
  - `notification-ui-bell`
  - `notification-ui-drawer`
  - `notification-feature-notifications`
- The `realtime` package's Flutter tests pass.

## DO-24: dispatch board, order queue and Home KPIs refresh live

- `libs/delivery/feature-dispatch` (inventory owns this page): only a constructor subscription was added. It debounces, then reloads the routes, the unassigned orders and the selected route.
- `libs/order/feature-orders`:
  - `order-queue.ts` now uses `changes$`
  - `order-detail.ts` reloads after a reconnect
- `apps/dashboard/src/app/home/home.ts` reloads on `dashboard.metrics_stale` and `order.status_changed`.

**Verified:** the lint and test targets pass for every project listed above.

## DO-38 / CA-18: token in the WebSocket URL

**What changed**

- `api/v1/routers/ws.py`:
  - The client sends `{"type":"auth","token":…}` as the first frame, and the server replies `{"type":"ready"}`.
  - A bad token closes the socket with 1008.
  - A token refresh is sent in-band and must keep the same user and tenant.
- **Transition:** `?token=` is still accepted so installed app builds keep working. Remove it once those builds are retired.
- Log redaction:
  - `config/logging.py` redacts token-like query parameters in the uvicorn and gunicorn access and error logs.
  - `backend/gunicorn.conf.py` installs the redaction in each worker.
  - `frontend/Caddyfile` has a comment: there is no access log, and it says how to filter tokens if one is ever enabled.
- Clients:
  - Dashboard: `websocket.service.ts`.
  - Mobile: `packages/realtime/lib/src/realtime_client.dart` uses the first-frame auth and has `pause`/`resume`, `updateAccessToken`, `onTokenRejected`, and a `reconnected` stream with resubscription.
  - Both apps' `main.dart` pause the socket while signed out, re-authenticate after a token refresh, and send a 1008 rejection through the API client's 401 → refresh path.

**Verified**

- `tests/unit/test_api_ws_auth.py`.
- The dashboard websocket spec.
- The `realtime` package tests check:
  - the URL has no token, and the first frame is the auth frame
  - the in-band token refresh
  - the 1008 callback
  - pause and resume
  - resubscription and the `reconnected` signal after a drop

## Feature 41 TASKS open items (`planning/features/41-*/TASKS.md`)

Both are fixed in `ws.py`, via `api/v1/dependencies/realtime.py`, which looks up ownership under RLS:

- **`driver` intent channel mismatch:** the intent now resolves to `driver:{Driver.id}`, the same channel that route events are published on.
- **No ownership check on `order:{id}`:**
  - staff need `orders:read`
  - a customer must own the order
  - drivers are refused

The boxes in that TASKS.md were deliberately left unticked, because this thread does not edit other planning docs. The lead should tick them on merge.

**Verified:** `tests/unit/test_api_ws_subscription_intents.py`.

## Reconnect, resubscribe and refetch (brief item 6)

Both clients back off from 1 s up to 30 s, resubscribe every active intent once `ready` arrives, and then trigger a refetch:

- Dashboard: `reconnected$`, consumed through `changes$()`.
- Mobile: `reconnected`, plus a `realtime.reconnected` marker on the change streams. The customer shell then refetches orders and invoices; the driver shell refetches its route, inbox and badge.

## Protocol (WebSocket)

- Client → server:
  - `{"type":"auth","token"}` as the first frame, and again later as a refresh
  - `{"subscribe":[…]}` once ready
  - `pong`
- Server → client:
  - `ready`
  - `ping`
  - `notification.new`, now with `created_at`
  - new: `notification.read` (with `notification_id`) and `notification.read_all`

## Changes in other engineers' areas (kept minimal)

- Orders: in `CancelOrderUseCase`, the pending-approval path now saves the order and records `CancellationRequested`. The unit test was updated to match.
- Inventory: one constructor block in `feature-dispatch.ts`.
- Dashboard home: the live reload in `home.ts`.
- Complaints: `feature-complaints.ts` opens the complaint named in `?complaint=`.
- Mobile shells: `app_shell.dart` (customer) has a 5-line reconnect refetch. The provider definitions changed, but the providers keep the same names and types, so the existing test overrides still work.

## Deferred

- Manual stock adjustments do not trigger the live low-stock alert, because `InventoryAdjusted` carries no `tenant_id`. The daily cron still covers them. Adding the field is a domain change for the inventory owner.
- The legacy `?token=` path stays for now; see DO-38.
- External channels (email, SMS and push) still need the arq worker to be running. In-app rows do not.

## ADR draft (for the lead to file in doc 15)

**ADR-0xx: in-app notifications written synchronously after commit; external channels in the worker.**

- **Context:** in-app alerts depended on the worker, so they silently disappeared whenever the worker was absent.
- **Decision:**
  - Domain-event handlers in the API process write the in-app rows in a fresh UoW, right after the business transaction commits.
  - Writing a row raises `notification.created` for the realtime fan-out.
  - Email, SMS and push are enqueued to arq with `in_app_delivered=true`.
  - Recipients are chosen by permission code plus branch scope under RLS, never by phone matching.
- **Consequences:**
  - Each action that notifies costs roughly one extra short transaction.
  - A failure to notify is logged and never fails the business action.

**ADR-0xx: WebSocket authentication by first frame.**

- **Context:** the token was sent in the URL, where proxies and servers log it.
- **Decision:**
  - The client authenticates with a first-frame auth message, the server replies `ready`, and failure closes with 1008.
  - The token is refreshed in-band and must keep the same user and tenant.
  - Query-parameter secrets are redacted in the uvicorn and gunicorn logs.
  - `?token=` is kept only as a transition path for installed apps.
- **Consequences:** clients must wait for `ready` before subscribing.
