-- ==========================================================================
-- PostgreSQL initialization — local development
--
-- Runs once, on first container start (empty data volume). To re-run:
--   docker compose -f infrastructure/docker/docker-compose.yml down -v
--
-- Establishes the role separation that tenant isolation depends on
-- (ADR-017, docs/architecture/06-database-architecture.md §2.2):
--
--   lpg_admin  — superuser. Migrations and administration only.
--   lpg_app    — the application role. NOT a superuser, NOT the table owner,
--                and explicitly WITHOUT BYPASSRLS.
--
-- This matters from day one. Row-Level Security is the backstop that holds
-- when application code is wrong; a role that can bypass it removes the
-- backstop entirely. Getting the roles right now costs nothing — retrofitting
-- them after tables exist is a migration with a security window in the middle.
-- ==========================================================================

\set ON_ERROR_STOP on

-- --------------------------------------------------------------------------
-- Extensions
-- --------------------------------------------------------------------------
-- pgcrypto: gen_random_uuid() is built into PG13+, but pgcrypto is still
-- required for digest/hmac used by future application-layer encryption.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- citext: case-insensitive text for email and similar identifiers.
CREATE EXTENSION IF NOT EXISTS citext;

-- pg_trgm: trigram matching, supporting fuzzy customer search alongside the
-- GIN/tsvector full-text strategy in docs/data/04-database-indexing.md.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- --------------------------------------------------------------------------
-- Application role
-- --------------------------------------------------------------------------
-- Role name and password are intentionally literal here rather than templated
-- from environment variables. Files in docker-entrypoint-initdb.d run through
-- psql, which does not expand shell environment variables, so an env-templated
-- role would silently fall back to defaults and produce a confusing mismatch
-- between .env and reality. These are local-development credentials with no
-- value outside the container; real environments provision roles through IaC.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lpg_app') THEN
        CREATE ROLE lpg_app
            WITH LOGIN
            PASSWORD 'dev_only_not_a_real_secret'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOBYPASSRLS
            INHERIT;
        RAISE NOTICE 'Created application role lpg_app (NOBYPASSRLS)';
    ELSE
        RAISE NOTICE 'Application role lpg_app already exists';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- Grants
-- --------------------------------------------------------------------------
-- Connect + schema usage. Table privileges are granted by migrations as
-- tables are created, so this stays a least-privilege baseline rather than a
-- blanket grant.
GRANT CONNECT ON DATABASE lpg_dev TO lpg_app;
GRANT USAGE ON SCHEMA public TO lpg_app;

-- Default privileges for objects the superuser creates later via migrations.
-- Note the deliberate absence of DELETE and UPDATE defaults: append-only
-- tables (audit_log, ledger_transaction, inventory_transaction) must have
-- those privileges withheld, and migrations grant them explicitly per table
-- where mutation is legitimate (06-database-architecture.md §6, §7).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO lpg_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO lpg_app;

-- --------------------------------------------------------------------------
-- Session variable used by RLS policies
-- --------------------------------------------------------------------------
-- Every request transaction issues:
--     SET LOCAL app.current_tenant_id = '<uuid>';
-- and every RLS policy predicates on current_setting('app.current_tenant_id').
--
-- Declaring the default here means current_setting() returns empty rather
-- than raising when the variable has not been set — so a query that forgets
-- to set tenant context returns NO ROWS instead of erroring. Failing closed
-- is the correct behaviour for a tenant-isolation backstop.
ALTER DATABASE lpg_dev SET app.current_tenant_id = '';

-- --------------------------------------------------------------------------
-- Test database
-- --------------------------------------------------------------------------
-- Integration tests run against a real PostgreSQL, never SQLite or a mock —
-- RLS policies and PostgreSQL-specific types must actually be exercised
-- (docs/implementation/testing-strategy.md).
SELECT 'CREATE DATABASE lpg_test OWNER lpg_admin'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'lpg_test')
\gexec

\connect lpg_test

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

GRANT CONNECT ON DATABASE lpg_test TO lpg_app;
GRANT USAGE ON SCHEMA public TO lpg_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO lpg_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO lpg_app;

ALTER DATABASE lpg_test SET app.current_tenant_id = '';
