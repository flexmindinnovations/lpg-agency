# 11 — API Contracts

## Purpose
Complete endpoint specifications: purpose, method, URL, headers, path/query parameters, request/response models, validation, permissions, business rules, status codes, error responses, pagination/filtering/sorting, and examples. No FastAPI implementation.

## Scope
Base path `/api/v1`. Every endpoint requires `Authorization: Bearer <JWT>` unless marked Public. Conventions per `10-api-design-guidelines.md`.

---

## Module: Authentication

### `POST /api/v1/auth/otp/request` — Public
**Purpose:** Request an OTP for Customer/Driver login.
**Headers:** `Content-Type: application/json`.
**Request:** `{ "phone_number": "+919876543210" }`
**Response `200 OK`:** `{ "otp_request_id": "...", "expires_in_seconds": 300 }`
**Validation:** valid phone format; rate-limited (5/hour/number).
**Errors:** `429 TOO_MANY_REQUESTS`.

### `POST /api/v1/auth/otp/verify` — Public
**Request:** `{ "otp_request_id": "...", "otp_code": "482913" }`
**Response `200 OK`:** `{ "access_token": "...", "refresh_token": "...", "expires_in": 900 }`
**Errors:** `401 OTP_MISMATCH`, `410 OTP_EXPIRED`.

### `POST /api/v1/auth/login` — Public (Staff)
**Request:** `{ "email": "...", "password": "..." }`
**Response `200 OK`:** token pair.
**Errors:** `401 INVALID_CREDENTIALS`, `423 ACCOUNT_LOCKED`.

### `POST /api/v1/auth/refresh`
**Request:** `{ "refresh_token": "..." }`
**Response `200 OK`:** new token pair.
**Errors:** `401 REFRESH_TOKEN_INVALID`.

---

## Module: Customers

### `POST /api/v1/customers`
**Purpose:** Create a customer (D-05 channels).
**Headers:** `Authorization`, `Idempotency-Key` (recommended).
**Request:** `{ "full_name", "phone_number", "customer_type", "branch_id", "primary_address": {"address_line", "latitude", "longitude"} }`
**Response `201 Created`:** Customer resource.
**Validation:** `full_name` 1–200 chars; `phone_number` E.164; `customer_type` enum.
**Permissions:** `customers:create`.
**Business Rules:** BR-22.
**Errors:** `400`, `409 DUPLICATE_PHONE`, `409 DUPLICATE_CONSUMER_NUMBER`.

### `GET /api/v1/customers/{customer_id}`
**Path Parameters:** `customer_id` (uuid).
**Permissions:** `customers:read` (Customer self-scoped; staff branch-scoped).
**Errors:** `404`.

### `GET /api/v1/customers`
**Query Parameters:** `phone_number`, `consumer_number`, `customer_type`, `status`, `branch_id`, `page`, `page_size`, `sort`.
**Permissions:** `customers:read` (staff only).

### `GET /api/v1/customers/{customer_id}/ledger`
**Purpose:** Real-time ledger balance + history.
**Query Parameters:** `from_date`, `to_date` (transaction history range), `cursor`, `limit`.
**Permissions:** `ledger:read`.
**Response `200 OK`:**
```json
{
  "customer_id": "c1...",
  "balances": [{"cylinder_type": "14.2kg Domestic", "status": "filled", "quantity": 1}],
  "transactions": {"items": [...], "page_info": {...}}
}
```

---

## Module: Orders

### `POST /api/v1/orders`
**Headers:** `Idempotency-Key` (recommended).
**Request:** `{ "customer_id", "address_id", "booking_source", "requested_date", "payment_method_preference", "lines": [{"cylinder_type_id", "quantity"}] }`
**Response `201 Created`:** Order, `status: "booked"`.
**Business Rules:** BR-04, BR-19.
**Permissions:** `orders:create`.
**Errors:** `400`; `409 CREDIT_LIMIT_EXCEEDED`; `409 CYLINDER_CAP_EXCEEDED`; `404`.

### `GET /api/v1/orders`
**Query Parameters:** `status`, `branch_id`, `from_date`, `to_date`, `customer_id`, `page`, `page_size`, `sort`.
**Permissions:** `orders:read`, role-scoped (Customer→self, Driver→assigned only, Dispatcher/Manager→branch).

### `GET /api/v1/orders/{order_id}`
**Permissions:** `orders:read`. **Errors:** `404`.

### `POST /api/v1/orders/{order_id}/deliver`
**Path Parameters:** `order_id`.
**Headers:** `Idempotency-Key` (strongly recommended — offline-sync retries).
**Request:** `{ "route_stop_id", "lines": [{"order_line_id", "quantity_delivered", "quantity_collected_empty"}], "proof_of_delivery": {"otp_code", "signature_blob_ref", "photo_blob_ref", "gps_lat", "gps_lng"}, "payment": {"method", "amount"} }`
**Response `200 OK`:** updated Order + `invoice_id` + `ledger_transaction_id`.
**Permissions:** `orders:deliver` (Driver, own route stop only).
**Business Rules:** BR-08, BR-13, BR-02.
**Errors:** `400` incomplete POD; `409 OTP_MISMATCH`; `409 INSUFFICIENT_VEHICLE_STOCK`.

### `POST /api/v1/orders/{order_id}/cancel`
**Request:** `{ "reason" }`
**Response:** `200 OK` (pre-dispatch) or `202 Accepted` (post-dispatch, pending approval).
**Permissions:** `orders:cancel`; post-dispatch requires `orders:cancel_approve`.

### `POST /api/v1/orders/bulk-cancel`
**Purpose:** Bulk cancellation (`10-api-design-guidelines.md` §8).
**Request:** `{ "order_ids": [...], "reason" }`
**Response `202 Accepted`:** `{ "job_id": "..." }` if > 50 items, else `200 OK` with per-item results.

---

## Module: Delivery / Routes

### `POST /api/v1/routes`
**Request:** `{ "branch_id", "driver_id", "vehicle_id", "route_date", "order_ids": [...] }`
**Response `201 Created`:** Route with ordered `stops[]`.
**Permissions:** `routes:create` (Dispatcher, Manager, AgencyAdmin).
**Business Rules:** BR-09.

### `GET /api/v1/routes`
**Query Parameters:** `driver_id`, `vehicle_id`, `route_date`, `status`, `page`, `page_size`.
**Permissions:** `routes:read`.

### `POST /api/v1/routes/{route_id}/load`
**Request:** `{ "lines": [{"cylinder_type_id", "filled_loaded", "empty_loaded"}] }`
**Permissions:** `inventory:load` (Warehouse Staff, Driver).
**Business Rules:** BR-12.

### `POST /api/v1/routes/{route_id}/reconcile`
**Request:** `{ "actual_filled", "actual_empty", "actual_cash", "variance_notes" }`
**Permissions:** `reconciliation:approve` (live-checked, D-16).
**Errors:** `403`.

---

## Module: Inventory

### `GET /api/v1/inventory-locations/{location_id}/balance`
**Permissions:** `inventory:read`.

### `POST /api/v1/inventory-locations/{location_id}/adjustments`
**Request:** `{ "cylinder_type_id", "from_status", "to_status", "quantity", "reason" }`
**Permissions:** `inventory:adjust` (claims-based; not one of the four live-checked actions in `17-api-security.md` §7 — `reconciliation:approve` above is).
**Errors:** `403`; `409 INSUFFICIENT_STOCK`; `409 INVALID_STATUS_TRANSITION`.

### `POST /api/v1/warehouses/{warehouse_id}/goods-receipt-notes`
**Request:** `{ "cylinder_type_id", "quantity_received", "source_omc" }`
**Permissions:** `inventory:load`.

---

## Module: Accounting

### `GET /api/v1/invoices/{invoice_id}`
**Permissions:** `invoices:read`.

### `GET /api/v1/invoices`
**Query Parameters:** `customer_id`, `status`, `from_date`, `to_date`, `page`, `page_size`.

### `POST /api/v1/invoices/{invoice_id}/payments`
**Request:** `{ "method", "amount", "gateway_transaction_ref" }`
**Response `201 Created`:** updated Invoice + Payment.
**Permissions:** `payments:create`.
**Errors:** `409 OVERPAYMENT`.

### `POST /api/v1/invoices/{invoice_id}/credit-notes`
**Request:** `{ "amount", "reason" }`
**Response `202 Accepted`:** CreditNote, `status: "requested"`.
**Permissions:** `credit_notes:request`.

### `PATCH /api/v1/credit-notes/{credit_note_id}/approve`
**Permissions:** `credit_notes:approve` (Manager/AgencyAdmin).

---

## Module: Complaints

### `POST /api/v1/complaints`
**Request:** `{ "customer_id", "reference_order_id", "category", "priority", "description" }`
**Response `201 Created`:** Complaint with server-computed `sla_due_at`.
**Permissions:** `complaints:create`.

### `GET /api/v1/complaints`
**Query Parameters:** `status`, `priority`, `category`, `sla_breached`, `page`, `page_size`.
**Permissions:** `complaints:read`.

### `POST /api/v1/complaints/{complaint_id}/resolve`
**Request:** `{ "outcome", "resolution_notes" }`
**Permissions:** `complaints:resolve`.

---

## Module: Reporting

### `GET /api/v1/reports/daily-sales`
**Query Parameters:** `date`, `branch_id`.
**Response `200 OK`:** aggregated totals + breakdown.

### `POST /api/v1/reports/{report_type}/exports`
**Response `202 Accepted`:** `{ "job_id" }`.

### `GET /api/v1/report-exports/{job_id}`
**Response:** job status + download URL when ready.

---

## Status Code Summary
| Code | Meaning |
|---|---|
| 200 | Successful read/update |
| 201 | Resource created |
| 202 | Accepted, async/pending-approval |
| 400 | Shape validation failure |
| 401 | Missing/invalid authentication |
| 403 | Authenticated, insufficient permission |
| 404 | Not found or not in caller's tenant |
| 409 | Business-rule conflict |
| 410 | Expired resource |
| 423 | Locked |
| 429 | Rate limited |
| 500 | Unexpected server error |

## Best Practices
- Every mutating endpoint documents cross-aggregate side effects explicitly.
- Approval-gated actions are distinct endpoints, never folded into a generic update.

## Risks
- Endpoint proliferation for approval workflows — mitigated by the consistent action-sub-resource convention.

## Alternatives Considered
- Generic `PATCH {status}` for all transitions — rejected in favor of explicit action endpoints.

## Future Scalability
- The action-sub-resource pattern extends cleanly to Phase 2 features without redesigning base resource contracts.
