#!/bin/sh
# Runs once, on first start of an empty Postgres volume (docker-entrypoint-initdb.d).
#
# Mirrors infrastructure/docker/postgres/init/01-init.sql (ADR-017) for production:
# the application connects as `lpg_app` — NOSUPERUSER, NOBYPASSRLS — so
# Row-Level Security stays an effective tenant-isolation backstop. Migrations
# run as the elevated `lpg_admin` role. The app password comes from the
# environment (LPG_APP_DB_PASSWORD); psql does not expand env vars in .sql
# files, hence a shell script passing it through `psql -v`.
set -eu

psql -v ON_ERROR_STOP=1 -v app_pw="$LPG_APP_DB_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

SELECT format(
    'CREATE ROLE lpg_app WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT',
    :'app_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lpg_app')
\gexec

REVOKE CONNECT ON DATABASE lpg FROM PUBLIC;
GRANT CONNECT ON DATABASE lpg TO lpg_app;
GRANT USAGE ON SCHEMA public TO lpg_app;

-- Least-privilege baseline; migrations grant UPDATE/DELETE per table where
-- mutation is legitimate (append-only tables must not get them by default).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO lpg_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO lpg_app;

-- Unset tenant context returns no rows instead of raising (fail closed).
ALTER DATABASE lpg SET app.current_tenant_id = '';
SQL
