-- Environment parity check for tenant isolation.
--
-- Six times now, a migration has created a tenant-scoped table and gotten its
-- isolation wiring wrong in a way no test caught: RLS enabled but not FORCEd
-- (owner bypasses it), a non-null-safe predicate that *raises* on an unscoped
-- connection, or a GRANT naming `lpg_app` literally so `lpg_uat` gets nothing.
-- Each was found by hand, after the fact, usually via a 500 in the UI.
--
-- This query finds all of them mechanically. Run it against every environment
-- after `alembic upgrade head`; every count must be 0.
--
-- Deliberately NOT checked: a `FOR ALL` policy with `USING` but no `WITH
-- CHECK`. That looks like a write-side hole and is not one — Postgres reuses
-- the USING expression as the write check when WITH CHECK is omitted. Most
-- tables here are in that shape, so flagging it would bury the real findings
-- under ~30 false positives.
--
--   docker exec -i lpg-postgres psql -U lpg_admin -d lpg_dev \
--       -f - < backend/scripts/verify_env_parity.sql
--
-- A table qualifies as tenant-scoped simply by having a `tenant_id` column,
-- so new schemas are covered automatically without touching this file.

WITH app_role AS (
    SELECT CASE current_database() WHEN 'lpg_uat' THEN 'lpg_app_uat' ELSE 'lpg_app' END AS r
),
tenant_tables AS (
    SELECT c.oid, n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'public', 'extensions',
                              -- Platform-owned schemas, present on Supabase only. They are
                              -- not ours to grant or to put RLS on.
                              'auth', 'storage', 'realtime', 'vault', 'graphql',
                              'graphql_public', 'supabase_functions', 'supabase_migrations',
                              'net', 'cron', 'pgsodium', 'pgsodium_masks')
      AND EXISTS (
          SELECT 1 FROM pg_attribute a
          WHERE a.attrelid = c.oid
            AND a.attname = 'tenant_id'
            AND a.attnum > 0
            AND NOT a.attisdropped
      )
)
SELECT
    current_database()                                                  AS db,
    count(*)                                                            AS tenant_tables,
    -- RLS switched off entirely.
    count(*) FILTER (WHERE NOT relrowsecurity)                          AS rls_off,
    -- Enabled but not forced: the owning role reads every tenant's rows.
    count(*) FILTER (WHERE relrowsecurity AND NOT relforcerowsecurity)  AS not_forced,
    -- RLS on with no policy denies everything; almost certainly unintended.
    count(*) FILTER (WHERE NOT EXISTS (
        SELECT 1 FROM pg_policy p WHERE p.polrelid = t.oid))            AS no_policy,
    -- ''::uuid raises; the NULLIF form degrades to "no rows" instead.
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM pg_policy p
        WHERE p.polrelid = t.oid
          AND pg_get_expr(p.polqual, p.polrelid) NOT LIKE '%NULLIF%'))  AS not_null_safe,
    -- The app role for *this* database cannot read the table at all.
    count(*) FILTER (WHERE NOT has_table_privilege(
        (SELECT r FROM app_role), t.oid, 'SELECT'))                     AS no_select_grant,
    -- Grants are checked across *every* application table, not just the
    -- tenant-scoped ones above. `identity.identity_user_permission` has no
    -- tenant_id and was missing its UAT grant for exactly that reason — the
    -- earlier version of this query could not see it.
    (SELECT count(*) FROM pg_class c
       JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind = 'r'
        AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'public', 'extensions',
                              -- Platform-owned schemas, present on Supabase only. They are
                              -- not ours to grant or to put RLS on.
                              'auth', 'storage', 'realtime', 'vault', 'graphql',
                              'graphql_public', 'supabase_functions', 'supabase_migrations',
                              'net', 'cron', 'pgsodium', 'pgsodium_masks')
        AND c.relname <> 'alembic_version'
        AND NOT has_table_privilege((SELECT r FROM app_role), c.oid, 'SELECT'))
                                                                        AS ungranted_tables
FROM tenant_tables t;
