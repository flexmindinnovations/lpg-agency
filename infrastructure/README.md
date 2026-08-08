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
| PostgreSQL 17 | `55432` | databases `lpg_dev`, `lpg_test` |
| Redis 7 | `56379` | cache, sessions, job queue, real-time backplane |

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

## Production infrastructure — not yet defined

This directory contains **no production infrastructure**, deliberately.

Azure is the target cloud, but the specific hosting topology (Container Apps
vs App Service vs other container hosting) and the IaC tool (Bicep vs
Terraform) are **explicitly deferred** to a decision before production
deployment — ADR-022, tracked as DW-05. Committing to a topology with no
running code, no measured load and no operational experience would be guessing.

One hard constraint the eventual choice must satisfy: the host must support
**long-lived WebSocket connections**, because real-time is Phase 1 scope
(ADR-015).

See `docs/architecture/13-deployment.md`.
