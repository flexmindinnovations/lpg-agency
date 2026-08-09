# Infrastructure

## Local development

`docker/docker-compose.yml` runs PostgreSQL and Redis for local development.

```bash
./scripts/dev-up.sh          # start
./scripts/dev-down.sh        # stop
./scripts/dev-down.sh --volumes   # stop and delete all local data
```

| Service | Host port | Notes |
|---|---|---|
| PostgreSQL 17 | `55432` | databases `lpg_dev`, `lpg_uat`, `lpg_test` |
| Redis 7 | `56379` | cache, sessions, job queue, real-time backplane |

### Environments

| Environment | Database | Where | Template |
|---|---|---|---|
| **dev** | `lpg_dev` | local Docker | `backend/.env.dev.example` |
| **uat** | `lpg_uat` | local Docker | `backend/.env.uat.example` |
| **test** | `lpg_test` | local Docker | used by the integration suite |
| **prod** | `postgres` | **Supabase cloud** (ADR-027) | `backend/.env.prod.example` |

dev and uat are separate *databases* on one instance rather than separate
instances: same engine version, same extensions, same role privileges, a
fraction of the resources. Each has its own `app.current_tenant_id` default and
its own `lpg_app` grants, so a mistake in one cannot reach the other.

Ports are deliberately non-default so this stack does not collide with a
PostgreSQL or Redis already running on your machine — a confusing failure mode
where the application connects successfully to entirely the wrong database.

### Database roles

`docker/postgres/init/01-init.sql` creates two roles, and the separation is
load-bearing rather than cosmetic (ADR-017,
`docs/architecture/06-database-architecture.md` §2.2):

| Role | Rights | Used by |
|---|---|---|
| `lpg_admin` | superuser | Alembic migrations, administration |
| `lpg_app` | `NOSUPERUSER`, **`NOBYPASSRLS`** | the application |

PostgreSQL Row-Level Security is the backstop that holds when application code
is wrong. An application role able to bypass RLS removes that backstop
entirely, so `lpg_app` must never be granted `BYPASSRLS` and must never own the
tables. Getting this right now costs nothing; retrofitting it after tables
exist is a migration with a security window in the middle.

The init script also sets a database-level default for
`app.current_tenant_id`. That makes `current_setting()` return empty rather
than raising when tenant context has not been set — so a query that forgets to
set it returns **no rows** instead of erroring. Failing closed is the correct
behaviour for a tenant-isolation backstop.

## Hosted database — Supabase

The **hosted** database is Supabase (ADR-027), as a managed PostgreSQL host and nothing more. Supabase Auth, Storage, Realtime and Edge Functions are not adopted.

Local development still uses the Docker Compose stack above. Keeping a local database means tests do not depend on network access or a shared remote, and preserves the environment parity Phase 1 established.

Two rules apply to the hosted database and are not optional:

1. **Alembic owns the schema.** Never change schema through Supabase's migration tooling, its SQL editor, or the MCP `apply_migration` tool. Those are for reading and diagnosis. `supabase/migrations/` must stay absent.
2. **Never connect the application as `service_role` or `postgres`.** The `service_role` key bypasses RLS by design, which removes the tenant-isolation backstop entirely. Provision a dedicated `NOSUPERUSER`, `NOBYPASSRLS` role, matching `lpg_app` locally.

### Supabase CLI

Installed via `npm install -g supabase` — **not** Homebrew, which is
macOS/Linux only and cannot run on this Windows development machine.

The CLI is a **diagnosis and inspection tool here, not part of the workflow**.
ADR-027 makes Alembic the sole owner of schema, which rules out a large part of
what the CLI normally does:

| Safe to use | Must not be used |
|---|---|
| `supabase projects list` | `supabase db push` — applies Supabase migrations |
| `supabase db dump` (inspection, backups) | `supabase migration new` — creates a second migration system |
| `supabase inspect db …` (query and index diagnosis) | `supabase db reset` — destroys schema Alembic owns |
| `supabase status`, `supabase link` | `supabase start` — duplicates the Docker Compose stack above |

`supabase/migrations/` must stay absent, and repository CI fails if it appears.
Two migration systems on one database produce a schema neither can reliably
describe.

### Supabase MCP server

Configured at project scope in `.mcp.json`. Also a development and diagnosis
tool; not part of the runtime. Its `apply_migration` tool is subject to the
same rule as `supabase db push` — do not use it for schema.

## Production infrastructure — not yet defined

This directory contains **no production infrastructure**, deliberately.

Azure remains the target cloud for **application** hosting (the database is on
Supabase, per ADR-027), but the specific hosting topology (Container Apps vs
App Service vs other container hosting) and the IaC tool (Bicep vs
Terraform) are **explicitly deferred** to a decision before production
deployment — ADR-022, tracked as DW-05. Committing to a topology with no
running code, no measured load and no operational experience would be guessing.

One hard constraint the eventual choice must satisfy: the host must support
**long-lived WebSocket connections**, because real-time is Phase 1 scope
(ADR-015).

See `docs/architecture/13-deployment.md`.
