# 03 — Database Schema (PostgreSQL)

## Purpose
Complete PostgreSQL physical schema: every table's purpose, columns, types, nullability, defaults, keys, constraints, indexes, audit fields, soft-delete strategy, tenant strategy, relationships, business rules, and example records.

## Scope
All tables across 9 PostgreSQL schemas (`tenant`, `customer`, `orders`, `delivery`, `inventory`, `ledger`, `accounting`, `complaints`, `identity`, `audit`).

## Design Decisions
- **Domain model vs. persistence model are distinct**: Python domain aggregates (`01-domain-model.md`) are plain objects; SQLAlchemy 2.x ORM models are a separate persistence-mapping concern (Repository pattern translates between them) — so the tables below are the *persistence* shape, which may differ in minor ways (e.g., denormalized projection tables) from the pure domain model.
- **UUIDs as primary keys**: `uuid` generated via `gen_random_uuid()` (pgcrypto/pgcrypto-free `gen_random_uuid()` built into PG13+), not serial integers — safe for offline-first client-side ID generation (Driver App) and no cross-tenant collision risk.
- **Tenant isolation**: every tenant-scoped table has `tenant_id uuid NOT NULL` protected by a **Row-Level Security (RLS) policy**, set via `SET LOCAL app.current_tenant_id = '<uuid>'` at the start of every request's transaction (a FastAPI dependency sets this from the JWT claim before any query executes) — defense in depth alongside application-layer repository scoping.
- **Soft delete**: `is_deleted boolean NOT NULL DEFAULT false` + `deleted_at timestamptz` + `deleted_by uuid` on business-meaningful entities; append-only tables have no delete path at all (enforced via `REVOKE DELETE, UPDATE` from the application's PostgreSQL role).
- **Audit fields**: `created_at timestamptz NOT NULL DEFAULT now()`, `created_by uuid NOT NULL`, `updated_at timestamptz`, `updated_by uuid`.
- **Optimistic concurrency**: `version integer NOT NULL DEFAULT 1`, incremented on every update (application-managed, since PostgreSQL has no native `rowversion`) — SQLAlchemy 2.x's built-in `version_id_col` mechanism handles this automatically at the ORM layer.

## Standard Fields (Every Table, Not Repeated Per Table)

| Field | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | Primary key |
| `tenant_id` | uuid | No* | session/app context | Tenant isolation; *nullable only on `identity.identity_user` for Super Admin |
| `created_at` | timestamptz | No | `now()` | Audit |
| `created_by` | uuid | No | current user | Audit |
| `updated_at` | timestamptz | Yes | null | Audit |
| `updated_by` | uuid | Yes | null | Audit |
| `is_deleted` | boolean | No | `false` | Soft delete flag |
| `deleted_at` / `deleted_by` | timestamptz / uuid | Yes | null | Soft delete audit pair |
| `version` | integer | No | `1` | Optimistic concurrency |

---

## Schema: `tenant`

### `tenant.tenant`
**Purpose:** Root multi-tenancy entity.

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| name | text | No | — | length 1–200 |
| slug | text | No | — | unique, URL-safe (predates this doc — Phase 2's original migration, never previously documented here) |
| status | text | No | `'trial'` | CHECK IN ('trial','active','suspended','closed') |
| subscription_plan | text | No | `'standard'` | — |
| primary_contact_email | text | No | — | valid email format (CHECK via regex) |
| country | char(2) | No | `'IN'` | ISO 3166-1 alpha-2 |

**PK:** `id`. **Unique:** `slug`. **Indexes:** `idx_tenant_status`.
**Relationships:** parent of branch, warehouse, tenant_configuration, cylinder_type, and (transitively) everything tenant-scoped.
**Business Rules:** never hard-deleted; `closed` is terminal.
**Example:** `{name: "Sunrise Gas Agency", status: "active", country: "IN"}`

### `tenant.branch`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK → tenant.tenant |
| name | text | No | — | — |
| region | text | Yes | null | — |

**Indexes:** `idx_branch_tenant_id`.
**Example:** `{name: "Nashik West Branch", region: "Maharashtra"}`

### `tenant.warehouse`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK |
| branch_id | uuid | No | — | FK → tenant.branch |
| name | text | No | — | — |
| address_line | text | No | — | — |

**Indexes:** `idx_warehouse_tenant_branch`.

### `tenant.tenant_configuration`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK |
| config_key | text | No | — | must match recognized key catalog |
| config_value | jsonb | No | — | shape validated per key |
| effective_from | timestamptz | No | — | no overlapping ranges per key |

**Unique:** `uq_tenant_config_key_effective (tenant_id, config_key, effective_from)`.
**Business Rules:** BR-31 — never hardcoded; historized so past transactions reference the value in effect at the time.
**Example:** `{config_key: "gst_rate_percent", config_value: "5.0", effective_from: "2026-04-01"}`
**Design Decision:** `config_value` is `jsonb` (not `text`) so numeric, string, and structured config values are all representable and independently queryable via PostgreSQL's JSONB operators without a schema change per new config type — see `04-database-indexing.md` §5 for the GIN index this enables.

### `tenant.cylinder_type`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK |
| name | text | No | — | unique per tenant |
| weight_kg | numeric(6,2) | No | — | CHECK > 0 |
| is_active | boolean | No | `true` | — |

**Example:** `{name: "14.2kg Domestic", weight_kg: 14.20}`

### `tenant.price_list` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK → tenant.tenant |
| cylinder_type_id | uuid | No | — | FK → tenant.cylinder_type |
| customer_type | text | No | — | CHECK IN ('domestic','commercial','industrial','government') |
| branch_id | uuid | Yes | null | FK → tenant.branch; null = tenant-wide default |
| price | numeric(10,2) | No | — | CHECK > 0 |
| effective_from | timestamptz | No | — | — |

**Unique:** `uq_price_list_dimension_effective (tenant_id, cylinder_type_id, customer_type, branch_id, effective_from)` — `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+), so a plain `UNIQUE` constraint's "NULL is never equal to NULL" semantics can't silently admit duplicate tenant-wide (`branch_id IS NULL`) default rows for the same dimension.
**Business Rules:** historized, same pattern as `tenant_configuration` — "changing" a price inserts a new row with a later `effective_from`, never an update. A branch-specific row overrides the tenant-wide default (`branch_id IS NULL`) for the same key at the same point in time; resolved by `EffectivePriceResolver` (`01-domain-model.md` §5). Chosen over folding price into `tenant_configuration`'s jsonb blob because it has a real lookup dimension (cylinder type x customer type x optional branch) that Order Management (Phase 10) will query directly.
**Example:** `{cylinder_type_id: "...", customer_type: "domestic", branch_id: null, price: 950.00, effective_from: "2026-04-01"}`

### `tenant.feature_flag_override`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK → tenant.tenant |
| flag_key | text | No | — | FK → platform.feature_flag.key |
| is_enabled | boolean | No | — | — |

**Unique:** `uq_feature_flag_override_tenant_flag (tenant_id, flag_key)`. **RLS:** standard tenant-isolation policy.
**Business Rules:** an explicit override always wins over the platform default/rollout for that tenant. Lives in `tenant` (not `platform`) because it's tenant-owned data, even though it references a `platform.feature_flag` row — see `FeatureFlagService`, `01-domain-model.md` §5, for the full precedence order (schedule → override → default → rollout percentage).
**Example:** `{flag_key: "sms_reminders_enabled", is_enabled: true}`

---

## Schema: `platform`
**New in Phase 7** — holds genuinely cross-tenant reference data, following the same non-RLS-reference-data precedent `identity.role`/`identity.permission` already established. Write access is enforced at the application layer, not by database grants (see `feature_flag`'s Design Decision below).

### `platform.feature_flag`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| key | text | No | — | PK |
| description | text | No | — | max length 500 |
| is_enabled_by_default | boolean | No | `false` | — |
| rollout_percentage | integer | Yes | null | CHECK BETWEEN 0 AND 100; null = 100 (no gradual rollout) |
| starts_at | timestamptz | Yes | null | scheduling: flag inactive before this time |
| ends_at | timestamptz | Yes | null | scheduling: flag inactive after this time |

**PK:** `key`. **RLS:** none — see schema note above.
**Design Decision:** SELECT is granted broadly (every request needs to evaluate flags); INSERT/UPDATE are granted to the application role too, but gated by a live permission check (`feature_flags:manage_platform`, `super_admin` only) in the use case layer — the same high-sensitivity live-recheck pattern `reconciliation:approve` uses, since the application always connects to Postgres as one role regardless of which user is authenticated.
**Example:** `{key: "sms_reminders_enabled", is_enabled_by_default: false, rollout_percentage: 25}`

---

## Schema: `customer`

### `customer.customer`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK |
| branch_id | uuid | No | — | FK |
| consumer_number | text | No | — | unique per tenant (BR-22) |
| full_name | text | No | — | length 1–200 |
| phone_number | text | No | — | unique per tenant, E.164 format |
| customer_type | text | No | `'domestic'` | CHECK IN ('domestic','commercial','industrial','government') |
| kyc_status | text | No | `'pending'` | CHECK IN ('pending','verified','rejected','expired') |
| status | text | No | `'active'` | CHECK IN ('active','inactive','blocked','closed') |
| search_vector | tsvector | Yes | generated | full-text search over full_name (`04-database-indexing.md` §5) |

**Unique:** `uq_customer_tenant_consumer_number`, `uq_customer_tenant_phone`.
**Indexes:** `idx_customer_tenant_phone`, GIN on `search_vector`.
**Business Rules:** BR-22, FR-CM-07 (never hard-deleted), BR-34 (closure sequence).
**Example:** `{consumer_number: "CN-004821", full_name: "Ramesh Patil", customer_type: "domestic"}`

### `customer.customer_address`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| customer_id | uuid | No | — | FK |
| address_line | text | No | — | — |
| latitude / longitude | numeric(9,6) | Yes | null | valid range if present |
| is_primary | boolean | No | `false` | partial unique index: max one true per customer |

### `customer.kyc_document`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| customer_id | uuid | No | — | FK |
| doc_type | text | No | — | — |
| doc_reference | text | No | — | app-layer encrypted |
| verification_status | text | No | `'pending'` | CHECK IN ('pending','verified','rejected') |
| verified_by | uuid | Yes | null | FK → identity_user |
| verified_at | timestamptz | Yes | null | — |

---

## Schema: `orders`

### `orders.order`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, branch_id | uuid | No | — | FKs |
| customer_id | uuid | No | — | FK |
| address_id | uuid | No | — | FK |
| status | text | No | `'draft'` | CHECK IN (10-state enum, lowercase snake_case) |
| booking_source | text | No | — | CHECK IN ('mobile_app','staff','phone','walk_in','whatsapp','api') |
| payment_method_preference | text | Yes | null | — |
| requested_date | timestamptz | No | — | not in the past at creation |
| metadata | jsonb | Yes | `'{}'` | extensible order metadata without schema change |

**Indexes:** `idx_order_tenant_status_date`, `idx_order_tenant_customer`, `idx_order_tenant_branch_status`.
**Business Rules:** BR-07 (state machine), BR-04/BR-19 (checked before confirmed).
**Example:** `{status: "confirmed", booking_source: "mobile_app", requested_date: "2026-08-10"}`

### `orders.order_line`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| order_id | uuid | No | — | FK |
| cylinder_type_id | uuid | No | — | FK |
| quantity_ordered | integer | No | — | CHECK > 0 |
| quantity_delivered | integer | No | `0` | CHECK >= 0 |
| quantity_pending | integer | No | `0` | CHECK >= 0 |
| is_backordered | boolean | No | `false` | — |

**Check Constraint:** `ck_orderline_quantity_consistency (quantity_delivered + quantity_pending <= quantity_ordered)`.

### `orders.order_status_history` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| order_id | uuid | No | — | FK |
| from_status | text | Yes | null | — |
| to_status | text | No | — | — |
| changed_by | uuid | No | — | FK |
| changed_at | timestamptz | No | `now()` | — |
| reason | text | Yes | null | — |

### `orders.failed_delivery_record`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| order_id | uuid | No | — | FK |
| reason_code | text | No | — | CHECK IN 5 values |
| resolution_action | text | Yes | null | CHECK IN ('reschedule','cancel','return_stock') |

### `orders.cancellation_record`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| order_id | uuid | No | — | FK |
| cancelled_by | uuid | No | — | FK |
| approved_by | uuid | Yes | null | required if post-dispatch |
| cancellation_charge | numeric(12,2) | Yes | null | — |
| reason | text | No | — | — |

---

## Schema: `delivery`

### `delivery.driver`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, branch_id | uuid | No | — | FKs |
| identity_user_id | uuid | No | — | FK, unique |
| license_number | text | No | — | — |
| status | text | No | `'active'` | CHECK IN ('active','on_leave','inactive') |

### `delivery.vehicle`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, branch_id | uuid | No | — | FKs |
| registration_number | text | No | — | unique per tenant |
| ownership_type | text | No | `'owned'` | CHECK IN ('owned','third_party','rental','gig') |
| capacity_units | integer | No | — | CHECK > 0 |
| status | text | No | `'active'` | CHECK IN ('active','maintenance','inactive') |

### `delivery.route`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, branch_id | uuid | No | — | FKs |
| driver_id, vehicle_id | uuid | No | — | FKs |
| route_date | date | No | — | — |
| shift_number | smallint | No | `1` | — |
| status | text | No | `'planned'` | CHECK IN 5 values |

**Indexes:** `idx_route_tenant_date_driver`, `idx_route_tenant_vehicle_date`.

### `delivery.route_stop`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| route_id | uuid | No | — | FK |
| order_id | uuid | No | — | FK |
| sequence_number | integer | No | — | unique per route |
| status | text | No | `'pending'` | CHECK IN 4 values |

### `delivery.proof_of_delivery`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| route_stop_id | uuid | No | — | FK, unique |
| otp_verified | boolean | No | — | must be true before delivered |
| signature_blob_ref | text | No | — | — |
| photo_blob_ref | text | No | — | — |
| gps_lat / gps_lng | numeric(9,6) | No | — | valid range |
| delivered_at | timestamptz | No | — | — |

**Business Rules:** BR-08, BR-23 — all fields required together.

### `delivery.vehicle_load_event` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| route_id, vehicle_id, cylinder_type_id | uuid | No | — | FKs |
| filled_loaded, empty_loaded | integer | No | `0` | CHECK >= 0 |
| loaded_at | timestamptz | No | `now()` | — |

### `delivery.vehicle_shift_reconciliation`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| route_id | uuid | No | — | FK, unique |
| expected_filled/actual_filled/expected_empty/actual_empty | integer | No | — | — |
| expected_cash/actual_cash | numeric(12,2) | No | — | — |
| variance_notes | text | Yes | null | — |
| approved_by | uuid | Yes | null | must hold WarehouseManager/AgencyAdmin permission (D-16) |

---

## Schema: `inventory`

### `inventory.inventory_location`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | No | — | FK |
| location_type | text | No | — | CHECK IN ('warehouse','vehicle') |
| location_ref_id | uuid | No | — | app-layer FK (polymorphic — see Risks) |

### `inventory.inventory_balance`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| inventory_location_id, cylinder_type_id | uuid | No | — | FKs |
| status | text | No | — | CHECK IN 7-state model |
| quantity | integer | No | `0` | CHECK >= 0 |
| last_transaction_id | uuid | No | — | FK |

**Business Rules:** materialized projection, updated only within the same transaction as its source `inventory_transaction` insert.

### `inventory.inventory_transaction` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, inventory_location_id, cylinder_type_id | uuid | No | — | FKs |
| transaction_type | text | No | — | CHECK IN 8 values |
| from_status | text | Yes | null | — |
| to_status | text | No | — | — |
| quantity | integer | No | — | CHECK > 0 |
| reference_order_id | uuid | Yes | null | FK |
| performed_by | uuid | No | — | FK |
| performed_at | timestamptz | No | `now()` | partition key (`19-data-migration.md`) |

### `inventory.goods_receipt_note`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, warehouse_id, cylinder_type_id | uuid | No | — | FKs |
| quantity_received | integer | No | — | CHECK > 0 |
| source_omc | text | Yes | null | CHECK IN ('iocl','bpcl','hpcl','other') |
| received_by | uuid | No | — | FK |
| received_at | timestamptz | No | `now()` | — |

### `inventory.reconciliation_record`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| inventory_location_id, cylinder_type_id | uuid | No | — | FKs |
| expected_quantity, actual_quantity | integer | No | — | — |
| variance | integer | GENERATED ALWAYS AS (actual_quantity - expected_quantity) STORED | — | — |
| approved_by | uuid | No | — | must hold restricted permission |

---

## Schema: `ledger`

### `ledger.cylinder_ledger`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, customer_id | uuid | No | — | FK, unique together |

### `ledger.ledger_balance`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| cylinder_ledger_id, cylinder_type_id | uuid | No | — | FKs |
| status | text | No | — | CHECK IN ('filled','empty','damaged') |
| quantity | integer | No | `0` | CHECK >= 0 |
| last_transaction_id | uuid | No | — | FK |

### `ledger.ledger_transaction` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, cylinder_ledger_id, cylinder_type_id | uuid | No | — | FKs |
| transaction_type | text | No | — | CHECK IN 7 values |
| filled_delta, empty_delta | integer | No | `0` | signed |
| reference_order_id | uuid | Yes | null | FK |
| performed_by | uuid | No | — | FK |
| performed_at | timestamptz | No | `now()` | partition key |
| notes | text | Yes | null | — |

**Business Rules:** BR-01–BR-06 — no transaction may drive a balance negative; "the most important module" per SRS.
**Example:** `{transaction_type: "exchange", filled_delta: 1, empty_delta: -1}`

---

## Schema: `accounting`

### `accounting.invoice`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, order_id, customer_id | uuid | No | — | FKs, order_id unique |
| subtotal_amount, tax_amount, total_amount | numeric(12,2) | No | `0` | total = subtotal+tax (CHECK) |
| currency | char(3) | No | `'INR'` | — |
| status | text | No | `'draft'` | CHECK IN 6 values |
| issued_at | timestamptz | No | — | immutable once set |

**Example:** `{subtotal_amount: 850.00, tax_amount: 42.50, total_amount: 892.50, status: "paid"}`

### `accounting.payment` **[Append-Only]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, invoice_id | uuid | No | — | FKs |
| method | text | No | — | CHECK IN ('cash','upi','card','online_gateway','credit') |
| amount | numeric(12,2) | No | — | CHECK > 0 |
| collected_by | uuid | No | — | FK |
| gateway_transaction_ref | text | Yes | null | required if method in (card, online_gateway) |
| collected_at | timestamptz | No | `now()` | — |

### `accounting.credit_note`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, invoice_id | uuid | No | — | FKs |
| amount | numeric(12,2) | No | — | CHECK > 0 |
| reason | text | No | — | — |
| requested_by | uuid | No | — | FK |
| approved_by | uuid | Yes | null | FK |
| status | text | No | `'requested'` | CHECK IN 4 values |

### `accounting.cash_handover`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, driver_id, route_id | uuid | No | — | FKs, route_id unique |
| amount_handed_over, expected_amount | numeric(12,2) | No | — | — |
| shortfall_status | text | Yes | `'none'` | CHECK IN 5 values |

---

## Schema: `complaints`

### `complaints.complaint`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id, customer_id | uuid | No | — | FKs |
| reference_order_id | uuid | Yes | null | FK |
| category | text | No | — | must match tenant category list |
| priority | text | No | `'medium'` | CHECK IN ('low','medium','high','critical') |
| status | text | No | `'open'` | CHECK IN 6 values |
| sla_due_at | timestamptz | No | computed at insert | BR-33 |
| description | text | No | — | length 1–2000 |

**Indexes:** `idx_complaint_tenant_status_sla`.

### `complaints.complaint_assignment` / `complaint_resolution` / `complaint_feedback`
Standard child entities — see `06-data-dictionary.md`.

---

## Schema: `identity`

### `identity.identity_user`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| tenant_id | uuid | Yes | null | null only for Super Admin |
| branch_id | uuid | Yes | null | FK → tenant.branch(id) — added Phase 7, once `tenant.branch` existed; deliberately left dangling (no FK) by Phase 6 |
| email | text | Yes | null | unique partial index where not null |
| phone_number | text | Yes | null | unique per tenant partial index |
| password_hash | text | Yes | null | null for OTP-only accounts |
| is_active | boolean | No | `true` | — |

### `identity.role` / `permission` / `user_role` / `role_permission`
Reference/junction tables — see `05-reference-data.md` §7–8.

---

## Schema: `audit`

### `audit.audit_log` **[Append-Only, bigint identity PK]**
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| id | bigint GENERATED ALWAYS AS IDENTITY | No | auto | PK |
| tenant_id | uuid | No | — | not FK-enforced (decoupled by design) |
| entity_name | text | No | — | — |
| entity_id | uuid | No | — | — |
| action | text | No | — | CHECK IN ('create','update','delete','login','login_failed','config_change') |
| performed_by | uuid | No | — | — |
| performed_at | timestamptz | No | `now()` | partition key |
| before_state | jsonb | Yes | null | — |
| after_state | jsonb | Yes | null | — |

**Protection:** application PostgreSQL role has `REVOKE UPDATE, DELETE` on this table (BR-28, D-39).

## Risks
- Polymorphic `inventory_location.location_ref_id` is not a physical FK — mitigated by application validation + periodic integrity job.
- Materialized `inventory_balance`/`ledger_balance` drifting from source transaction logs — mitigated by same-transaction updates only, plus periodic reconciliation.
- RLS policy gaps on newly-added tables — mitigated by migration-review checklist (`19-data-migration.md`).

## Alternatives Considered
- `jsonb` EAV-style config only for `tenant_configuration` (not the whole schema) — deliberate, scoped exception to support arbitrary future config keys without migrations; the rest of the schema stays fully normalized relational.
- Serial/bigint PKs instead of UUID — rejected except for `audit_log` (pure append-order scan, no offline-client-ID requirement).

## Best Practices
- Every schema change via **Alembic** migration, code-reviewed (`19-data-migration.md`), never manual DDL in production.
- No cross-schema FK creating circular bounded-context dependencies — cross-context references are ID-only.

## Future Scalability
- Every bounded-context schema can be extracted to a physically separate PostgreSQL database (or even a different engine) with minimal change since cross-schema references are ID-only.
