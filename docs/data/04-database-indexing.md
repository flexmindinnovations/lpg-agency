# 04 — Database Indexing

## Purpose
Designs every index in the PostgreSQL schema — primary, composite, partial, covering, full-text, JSONB, GIN/GIST — with explicit rationale for each.

## Scope
Extends `03-database-schema.md`'s per-table constraint notes; organized here by index type.

## 1. Primary Indexes

Every table's primary key (`id uuid`) automatically creates a unique B-tree index. PostgreSQL has no separate "clustered index" concept like SQL Server (tables are heap-organized by default) — `CLUSTER` can physically reorder a table on a chosen index, but this is a one-time operation, not maintained automatically. **Decision: do not use `CLUSTER`** for any table in Phase 1 — PostgreSQL's heap storage with well-chosen secondary indexes (below) is sufficient, and `CLUSTER` requires an exclusive lock and manual re-running, operationally awkward for high-write append-only tables.

## 2. Composite Indexes (Tenant-Leading Principle)

**Universal rule:** every non-PK index on a tenant-scoped table **leads with `tenant_id`**, even when the query's primary filter appears to be another column. At the platform's target scale (thousands of tenants sharing one database), this keeps each tenant's rows physically co-located within the index's leaf pages, preventing cross-tenant page scanning.

| Index | Table | Why |
|---|---|---|
| `idx_tenant_status` | tenant.tenant | Super Admin dashboard filtering by lifecycle state |
| `idx_customer_tenant_phone` | customer.customer | OTP-login lookup + staff-assisted booking search — highest frequency |
| `idx_order_tenant_status_date` | orders.order | Order Queue view — the single highest-traffic query pattern |
| `idx_order_tenant_customer` | orders.order | Customer order history |
| `idx_order_tenant_branch_status` | orders.order | Branch-scoped operational dashboards |
| `idx_orderline_order_id` | orders.order_line | Parent-lookup for order detail views |
| `idx_route_tenant_date_driver` | delivery.route | "My routes today" + route-planning-by-date |
| `idx_route_tenant_vehicle_date` | delivery.route | Prevent double-booking a vehicle |
| `idx_inventorytxn_tenant_location_time` | inventory.inventory_transaction | Cylinder Movement Report + reconciliation |
| `idx_ledgertxn_tenant_ledger_time` | ledger.ledger_transaction | **The single most important index in the schema** — real-time balance verification, point-in-time reconstruction, consumption analysis |
| `idx_invoice_tenant_customer_status` | accounting.invoice | Outstanding Balance calculation (BR-19), checked on every booking |
| `idx_invoice_tenant_issued_at` | accounting.invoice | GST reporting and Daily Sales Report |
| `idx_payment_tenant_collectedby_time` | accounting.payment | Driver cash reconciliation |
| `idx_complaint_tenant_status_sla` | complaints.complaint | SLA Breach Scanner — runs every 15 min across potentially thousands of tenants |
| `idx_auditlog_tenant_entity` | audit.audit_log | "Show audit history for this record" |

**Column-order rationale examples:**
- `idx_order_tenant_status_date` orders `status` before `requested_date` because the Order Queue view always filters by status first, then sorts/filters by date within that status.
- `idx_ledgertxn_tenant_ledger_time` orders `cylinder_ledger_id` before `performed_at` because every ledger query scopes to one customer's ledger first, then orders chronologically within it.

## 3. Partial Indexes (PostgreSQL-Specific — Equivalent to SQL Server's Filtered Indexes)

| Index | Definition | Why |
|---|---|---|
| `uq_customeraddress_one_primary` | UNIQUE (customer_id) WHERE is_primary | Enforces "at most one primary address" without a full-table unique constraint |
| `uq_identityuser_email` | UNIQUE (email) WHERE email IS NOT NULL | Customer/Driver accounts may be phone-only (OTP) |
| `idx_order_tenant_active` | (tenant_id, status) WHERE NOT is_deleted | Order list views almost always exclude soft-deleted rows |
| `idx_customer_tenant_active` | (tenant_id, status) WHERE NOT is_deleted | Same rationale for the highest-cardinality customer-facing table |
| `idx_complaint_open_sla` | (tenant_id, sla_due_at) WHERE status NOT IN ('resolved','closed') | The SLA Breach Scanner only ever queries open complaints — scoped exactly to that predicate, smaller and faster than a full index |

## 4. Covering Indexes (INCLUDE Columns — Deliberately Deferred)

Covering indexes for the highest-traffic Dashboard list views are **not pre-defined at launch** — added post-launch based on `pg_stat_statements` and `EXPLAIN ANALYZE` output from real production query patterns, avoiding speculative write-amplification on high-volume append-only tables (`ledger_transaction`, `inventory_transaction`) before real usage data justifies the specific columns to include.

**Anticipated first candidates** (to validate post-launch): `idx_order_tenant_status_date` INCLUDE `(customer_id, booking_source)`; `idx_invoice_tenant_customer_status` INCLUDE `(total_amount)`.

## 5. JSONB Indexes (GIN)

| Index | Column | Why |
|---|---|---|
| `idx_tenantconfig_value_gin` | tenant.tenant_configuration.config_value (GIN, jsonb_path_ops) | Enables efficient containment queries if future features need to query inside configuration values, not just fetch by config_key |
| `idx_order_metadata_gin` | orders.order.metadata (GIN) | Supports ad-hoc filtering on extensible order metadata without a schema migration |

**Design principle:** JSONB + GIN used deliberately sparingly — only for genuinely schema-flexible fields, never as a substitute for proper relational columns on fields with known, stable structure (e.g., `order.status` remains a plain CHECK-constrained text column, not JSONB) — keeping core invariants enforceable by standard constraints, not application code inspecting JSON.

## 6. GIN/GIST for Full-Text Search

| Index | Column | Why |
|---|---|---|
| `idx_customer_search_gin` | customer.customer.search_vector (GIN, tsvector) | Staff name/phone search — PostgreSQL's native full-text search avoids the LIKE '%...%' performance cliff and the separate search-service dependency a SQL Server-based design would eventually need — PostgreSQL gets this "for free" at Phase 1. |

**GIST** is not currently used — reserved for future geospatial queries (e.g., "nearest warehouse to this delivery address" via PostGIS) if Phase 2 route optimization needs genuine geospatial indexing beyond simple lat/lng storage.

## 7. Unique Indexes (Enforcing Business Rules, Not Just Performance)

| Index | Table | Enforces |
|---|---|---|
| `uq_customer_tenant_consumer_number` | customer.customer | BR-22 — one active Consumer Number per customer per tenant |
| `uq_customer_tenant_phone` | customer.customer | Prevents duplicate registration by phone within a tenant |
| `uq_invoice_order_id` | accounting.invoice | D-10 — exactly one invoice per delivered order |
| `uq_routestop_route_sequence` | delivery.route_stop | Prevents duplicate sequence positions within a route |
| `uq_pod_route_stop` | delivery.proof_of_delivery | One POD per stop |
| `uq_cylinderledger_tenant_customer` | ledger.cylinder_ledger | One ledger per customer |
| `uq_vehicle_tenant_registration` | delivery.vehicle | Prevents duplicate vehicle registration within a tenant |
| `uq_driver_identity_user` | delivery.driver | One driver record per identity account |
| `uq_tenantconfig_key_effective` | tenant.tenant_configuration | Prevents overlapping effective-date ranges for the same key |

## Best Practices
- No index exists without a documented query pattern (this document *is* that documentation).
- `ledger_transaction` and `inventory_transaction` are kept deliberately lean (two B-tree indexes each) — the highest-write tables, where over-indexing directly threatens delivery-confirmation latency.
- Index maintenance via `autovacuum`/`autoanalyze` tuning (more aggressive thresholds on high-write append-only tables), monitored via `pg_stat_user_indexes`.

## Risks
- **Over-indexing high-write tables** — mitigated by the lean, justified-only approach.
- **GIN index write overhead**: more expensive to maintain than B-tree on write — mitigated by narrow scope (§5).
- **Wrong composite column order** — silently degrades to a sequential scan; mitigated by `pg_stat_statements` + `EXPLAIN ANALYZE` monitoring post-launch.

## Alternatives Considered
- Serial/bigint PKs for insertion-order clustering benefit — rejected in favor of UUIDs for offline-client-ID-generation safety; PostgreSQL's heap storage doesn't suffer the same GUID-fragmentation penalty SQL Server's clustered-index model does, making this trade-off less costly than on SQL Server.
- External search service (Elasticsearch/Azure Cognitive Search) for customer search — deferred; PostgreSQL full-text search (§6) is sufficient at Phase 1 scale, avoiding an additional infrastructure dependency.

## Future Scalability
- Once table partitioning is introduced for the largest append-only tables (`19-data-migration.md`), indexes on those tables become partition-aligned automatically (PostgreSQL native partitioning creates per-partition indexes), improving query performance and maintenance (VACUUM/REINDEX) cost at very large scale.
- PostGIS + GIST become a natural addition if Phase 2 route optimization needs true geospatial queries.
