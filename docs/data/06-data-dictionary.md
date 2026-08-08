# 06 — Data Dictionary

## Purpose
Documents meaning, business purpose, validation, allowed values, default, nullability, business rules, and example for every field of consequence.

## Scope
Standard fields documented once (§1); high-complexity/high-business-value entities get full per-field treatment; simple reference/join tables are covered by `05-reference-data.md` and `03-database-schema.md`'s constraints.

## 1. Standard Fields (Every Table)

| Field | Meaning | Business Purpose | Nullable | Default | Example |
|---|---|---|---|---|---|
| `id` | Unique row identifier | Primary key, safe for offline client generation | No | `gen_random_uuid()` | `3fa85f64-...` |
| `tenant_id` | Owning tenant | Multi-tenant data isolation | No* | session claim | tenant uuid |
| `created_at` | Creation timestamp | Audit trail | No | `now()` | `2026-08-07T09:15:00Z` |
| `created_by` | Creator | Audit trail | No | current user | user uuid |
| `updated_at`/`updated_by` | Last update pair | Audit trail | Yes | null | — |
| `is_deleted` | Soft-delete flag | Preserve history while hiding from active views | No | `false` | `false` |
| `version` | Optimistic concurrency token | Detect stale concurrent writes | No | `1` | `3` |

## 2. Customer

| Field | Meaning | Business Purpose | Nullable | Default | Allowed Values | Business Rule | Example |
|---|---|---|---|---|---|---|---|
| `consumer_number` | Unique connection ID | Links customer to their LPG connection | No | none | tenant-defined format | BR-22 | "CN-004821" |
| `full_name` | Customer name | Identification, printed on documents | No | none | 1–200 chars | — | "Ramesh Patil" |
| `phone_number` | OTP-login number | Authentication + contact | No | none | E.164 format, unique/tenant | — | "+919876543210" |
| `customer_type` | Connection category | Drives pricing, cylinder cap, tax | No | 'domestic' | domestic/commercial/industrial/government | BR-04 | "domestic" |
| `kyc_status` | Verification state | Gates new-connection issuance (policy TBD) | No | 'pending' | pending/verified/rejected/expired | BR-21 | "verified" |
| `status` | Lifecycle state | Governs whether customer can transact | No | 'active' | active/inactive/blocked/closed | BR-34 | "active" |

## 3. Order / OrderLine

| Field | Meaning | Business Purpose | Nullable | Default | Allowed Values | Business Rule | Example |
|---|---|---|---|---|---|---|---|
| `status` | Lifecycle state | Drives all downstream workflow (route planning, invoicing) | No | 'draft' | 10-value enum | BR-07 | "confirmed" |
| `booking_source` | Origin channel | Analytics, reconciling call-center vs. self-service volume | No | none | 6-value enum | D-05 | "mobile_app" |
| `requested_date` | Delivery request date | Route planning input | No | none | not in the past | — | 2026-08-10 |
| `quantity_ordered` | Units requested | Basis for fulfillment tracking | No | none | > 0 | — | 1 |
| `quantity_delivered` | Units delivered so far | Partial fulfillment tracking | No | 0 | ≥ 0, ≤ ordered | D-08 | 1 |
| `quantity_pending` | Units still owed | Backorder tracking | No | 0 | ≥ 0 | D-08 | 0 |

## 4. Proof of Delivery

| Field | Meaning | Business Purpose | Nullable | Business Rule | Example |
|---|---|---|---|---|---|
| `otp_verified` | OTP confirmed by customer | Proves the right person received the delivery | No | BR-08/BR-23 | true |
| `signature_blob_ref` | Signature image reference | Legal proof of receipt | No | BR-08 | "blob://pod/....png" |
| `photo_blob_ref` | Delivery photo reference | Visual proof of delivery | No | BR-08 | "blob://pod/....jpg" |
| `gps_lat`/`gps_lng` | Delivery coordinates | Location verification, dispute resolution | No | valid range | 19.998 / 73.790 |

## 5. Ledger Transaction / Inventory Transaction

| Field | Meaning | Business Purpose | Nullable | Default | Allowed Values | Business Rule | Example |
|---|---|---|---|---|---|---|---|
| `transaction_type` (ledger) | Movement category | Distinguishes exchange from new purchase from deposit return, etc. | No | none | 7-value enum | D-09 | "exchange" |
| `filled_delta`/`empty_delta` | Signed balance change | The actual arithmetic effect on customer holding | No | 0 | signed int | BR-01–BR-06 | +1 / -1 |
| `transaction_type` (inventory) | Movement category | Distinguishes load/deliver/collect/adjust etc. | No | none | 8-value enum | BR-15 | "load" |
| `from_status`/`to_status` (inventory) | Cylinder condition transition | Tracks physical cylinder health lifecycle | from nullable | none | 7-value enum | D-14 | empty → damaged |
| `quantity` (inventory) | Units moved | Basis for all stock counting | No | none | > 0 | — | 5 |

## 6. Invoice / Payment

| Field | Meaning | Business Purpose | Nullable | Default | Allowed Values | Business Rule | Example |
|---|---|---|---|---|---|---|---|
| `total_amount` | Subtotal + Tax | Amount owed | No | 0 | ≥ 0 | must equal subtotal+tax | 892.50 |
| `status` (invoice) | Payment lifecycle | Determines outstanding balance calculations | No | 'draft' | 6-value enum | D-11 | "paid" |
| `method` (payment) | Payment channel | Reconciliation, driver cash tracking | No | none | 5-value enum | BR-18 | "cash" |
| `amount` (payment) | Amount collected | Basis for outstanding balance reduction | No | none | > 0, sum ≤ total minus credit notes | — | 892.50 |

## 7. Complaint

| Field | Meaning | Business Purpose | Nullable | Default | Allowed Values | Business Rule | Example |
|---|---|---|---|---|---|---|---|
| `category` | Classification | Routes to the right team, feeds reporting | No | none | tenant category list | — | "short_delivery" |
| `priority` | Urgency | Drives SLA calculation | No | 'medium' | low/medium/high/critical | — | "high" |
| `sla_due_at` | SLA deadline | Enforces service commitment | No | computed at insert | valid future timestamp | BR-33 | 2026-08-11T09:00Z |

## 8. Identity User

| Field | Meaning | Business Purpose | Nullable | Business Rule | Example |
|---|---|---|---|---|---|
| `tenant_id` | Owning tenant | Scopes staff to their agency | Yes | null only for Super Admin | tenant uuid or null |
| `email` | Staff login | Password/SSO authentication | Yes | required for that path | "manager@sunrisegas.in" |
| `phone_number` | Customer/Driver login | OTP authentication | Yes | required for that path | "+919876543210" |

## 9. Coverage Note
Fields not individually expanded above (junction tables, `driver`, `vehicle`, `goods_receipt_note`, `reconciliation_record`, `complaint_assignment/resolution/feedback`, `audit_log`) are self-descriptive from column names plus `03-database-schema.md`'s constraint definitions, which are authoritative for those fields to avoid duplicate-maintenance drift.

## Risks
- Dictionary/schema drift — mitigated by updating this document in the same PR as any Alembic migration.

## Alternatives Considered
- Auto-generated dictionary from PostgreSQL `COMMENT ON COLUMN` metadata — deferred as a future improvement until the schema stabilizes post-launch.

## Future Scalability
- Migrate to `COMMENT ON` as the field-description source of truth, with this document generated from it, once tooling investment is justified.
