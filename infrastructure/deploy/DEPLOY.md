# Deploying LPG Agency to a DigitalOcean Droplet

Single-host Docker Compose deployment: Postgres 17, Redis, the FastAPI backend, the arq background worker, a one-shot Alembic
migration job, and Caddy serving the Angular dashboard and reverse-proxying
`/api` + `/health` to the backend (same origin, so no CORS in practice).

| Item | Value |
|---|---|
| Public URL | `https://lpg.vitessetec.com` (HTTPS, Let's Encrypt) |
| Droplet public IP | `139.59.88.0` (the IP itself no longer serves the app - it redirects) |
| OS | Ubuntu 24.04 LTS, 1 vCPU, 2 GB RAM, 48 GB disk |
| SSH user | `root` (key auth only) |
| App directory | `/opt/lpg-agency` |
| Compose project | `lpg-agency` (files in `infrastructure/deploy/`) |

> **Status (2026-09-25).** Sections 1-6 were executed and verified: the stack
> deploys, all 86 migrations apply, the dashboard loads at `http://139.59.88.0/`
> and `/health/live` returns 200. `/health/ready` returns 503 only because
> object storage is not configured yet (see "Object storage" in section 5).
> Section 7 (first super_admin) is done; section 8 (HTTPS) is still open.

Commands prefixed `#` describe what follows. Lines in `bash` blocks are meant to
be copy-pasted one block at a time.

---

## 1. Connect to the droplet (from any machine)

The droplet only accepts SSH keys. Each machine you connect from needs its own
key authorised once.

On the **new machine**, create a key and print the public half:

```bash
ssh-keygen -t ed25519 -C "$(whoami)@$(hostname)"
cat ~/.ssh/id_ed25519.pub
```

Authorise it from a machine that already has access (or the DigitalOcean web
console: Droplet -> Access -> Launch Droplet Console):

```bash
# Append the new machine's public key so it can log in.
echo 'PASTE-THE-PUBLIC-KEY-HERE' >> ~/.ssh/authorized_keys
```

Connect:

```bash
ssh root@139.59.88.0
```

Optional shortcut in `~/.ssh/config` on your machine, so `ssh lpg` works:

```
Host lpg
  HostName 139.59.88.0
  User root
  IdentityFile ~/.ssh/id_ed25519
```

---

## 2. Prepare the server (one time) - DONE

Run on the droplet as root.

```bash
# Refresh package lists and install pending security/kernel updates.
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get -y upgrade
```

```bash
# Add a 2 GB swap file. 2 GB RAM is tight for Postgres + backend (OCR/ONNX) +
# the frontend build; swap keeps the OOM killer away. swappiness=10 means swap
# is used only under real memory pressure.
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf && sysctl -p /etc/sysctl.d/99-swap.conf
```

```bash
# Firewall: allow SSH first (so enabling it cannot lock you out), then web.
# Postgres/Redis are not published on the host, so nothing else is open.
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
```

```bash
# A kernel update was pending after the upgrade; reboot once, then reconnect.
reboot
```

### Install Docker Engine + Compose (official Docker apt repository)

```bash
# Trust Docker's package signing key.
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
# Register the Docker repository for this Ubuntu release.
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
```

```bash
# Install Docker Engine, the Compose v2 plugin and buildx, then verify.
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker --version && docker compose version
```

---

## 3. Let the server read the private GitHub repo (deploy key) - DONE

The droplet needs its own read-only credential to `git pull`. This is separate
from the key you use to SSH *into* the droplet.

```bash
# Generate a key that exists only on the droplet (no passphrase: it is used
# non-interactively by deploy.sh).
ssh-keygen -t ed25519 -C "lpg-droplet-github-deploy" -f ~/.ssh/lpg_github_deploy -N ""
```

```bash
# Make SSH use that key for github.com, and pre-trust GitHub's host key.
printf 'Host github.com\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/lpg_github_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
chmod 600 ~/.ssh/config
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
```

```bash
# Print the public key, then add it in GitHub:
# repo flexmindinnovations/lpg-agency -> Settings -> Deploy keys -> Add deploy key
# (title "lpg-droplet", leave "Allow write access" UNCHECKED).
cat ~/.ssh/lpg_github_deploy.pub
```

Current droplet deploy key (public half, safe to share):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILIZ4rWODJryJMPI5EbU56cbLBPEjQx+uW/DCVZJ3NNm lpg-droplet-github-deploy
```

```bash
# Test: should print "Hi flexmindinnovations/lpg-agency! You've successfully authenticated".
ssh -T git@github.com
```

---

## 4. Get the code onto the server

```bash
# Clone into /opt. Use -b <branch> for a branch other than the default.
git clone git@github.com:flexmindinnovations/lpg-agency.git /opt/lpg-agency
```

> The production files (`infrastructure/deploy/`, both Dockerfiles, the
> `LPG_DB_SSL_MODE` setting) must be on the branch you clone. Merge them to
> `main` first, or clone their branch with `-b`.

---

## 5. Create the secrets file (one time)

```bash
# Writes infrastructure/deploy/.env (mode 600, git-ignored) with generated
# database/Redis passwords, an RS256 JWT keypair and the KYC Fernet key.
# It refuses to overwrite an existing .env.
cd /opt/lpg-agency/infrastructure/deploy
chmod +x generate-env.sh deploy.sh postgres-init/01-init.sh
./generate-env.sh
```

**Back up `.env` off the server** (password manager or encrypted storage). The
database passwords are baked into the Postgres volume on first start, and losing
`LPG_KYC_ENCRYPTION_KEY` makes stored KYC references unreadable.

Optional extras you can append to `.env`: `WEB_CONCURRENCY=2` (gunicorn workers;
default 2), and `LPG_GEMINI_API_KEY=` if you want the AI assistant (also add it
to the `x-backend-env` block in `docker-compose.prod.yml`).


### Object storage: DigitalOcean Spaces

The backend stores uploads (proof-of-delivery photos, generated PDFs) in any
S3-compatible bucket. MinIO no longer publishes Docker images, so use Spaces:

1. DigitalOcean console -> Spaces Object Storage -> **Create a Space** (pick a
   region, e.g. `blr1`; note the name).
2. API -> **Spaces Keys** -> Generate New Key; copy the access key and secret.
3. Put them in `.env` on the server (endpoint is `https://<region>.digitaloceanspaces.com`):

```bash
nano /opt/lpg-agency/infrastructure/deploy/.env
```

```
LPG_STORAGE_ENDPOINT_URL=https://blr1.digitaloceanspaces.com
LPG_STORAGE_ACCESS_KEY=<spaces access key>
LPG_STORAGE_SECRET_KEY=<spaces secret>
LPG_STORAGE_BUCKET=<space name>
LPG_STORAGE_REGION=blr1
```

```bash
# Recreate the containers that read storage settings.
docker compose -f docker-compose.prod.yml up -d backend worker
```

Until these are set the app still starts, but `/health/ready` reports storage
as down and uploads/PDF generation fail.

---

## 6. First deploy

```bash
# Builds the backend and frontend images (the first build takes several
# minutes on 1 vCPU), runs Alembic migrations, then starts everything.
cd /opt/lpg-agency/infrastructure/deploy
./deploy.sh
```

Verify:

```bash
# All services Up/healthy; `migrate` should show Exited (0).
docker compose -f docker-compose.prod.yml ps
```

```bash
# Backend liveness/readiness through Caddy (readiness checks Postgres, Redis, storage).
curl -s http://localhost/health/live
curl -s http://localhost/health/ready
```

Then open `http://139.59.88.0/` in a browser.

---

## 7. First admin user (platform super_admin)

A fresh database has no users. `backend/scripts/bootstrap_super_admin.py`
creates the platform-level `super_admin` (no tenant; signs in to the Platform
Console) with a random password, printed once and stored nowhere. It is
idempotent - an existing email is left untouched, never reset. Do **not** use
`seed_dev_user.py` here: it creates a well-known dev password.

```bash
# Run the script inside the backend image, using the migration (admin) DSN.
cd /opt/lpg-agency/infrastructure/deploy
docker compose -f docker-compose.prod.yml run --rm --no-deps -T migrate     python scripts/bootstrap_super_admin.py --email super_agency@lpg.com
```

Copy the printed password into a password manager. The app currently has **no
change-password feature** (only forgot/reset by email, and no email provider is
configured), so this password stays until one is built.

Verify (from the droplet, so the password never crosses plain HTTP):

```bash
# Expect HTTP 200 with tokens, then 200 from /platform/agencies.
curl -s -H 'Content-Type: application/json'   -d '{"email":"super_agency@lpg.com","password":"<PASSWORD>"}' http://localhost/api/v1/auth/login
```

Agencies are created from the Platform Console (sign in as this super_admin ->
Agencies -> **Create agency**), or `POST /api/v1/platform/agencies`. It creates
the agency plus its first `agency_admin` and shows a one-time password-setup
link (no email provider is configured, so relay it yourself). The new admin
cannot sign in until you issue **and activate** a license under Licenses.
This needs migration `d5b9e3a7f1c4`; `./deploy.sh` applies it automatically.

---

## 8. Domain and HTTPS - DONE (2026-09-26)

The app is served at **https://lpg.vitessetec.com**. `vitessetec.com` is an
existing domain whose DNS is hosted by MilesWeb (cPanel account `zugjjztt`); a
subdomain of it is used until a dedicated domain is bought.

What was done, and how to repeat it for a new domain:

1. **DNS record** - one `A` record pointing the name at the droplet, TTL 300.
   Here: cPanel -> DNS Zone Editor -> `vitessetec.com` -> Add Record ->
   Type `A`, Name `lpg`, Address `139.59.88.0`. (DigitalOcean does not sell
   domains; it only hosts DNS. To use DigitalOcean DNS for a bought domain, add
   the domain under Networking -> Domains and set the registrar's nameservers to
   `ns1/ns2/ns3.digitalocean.com`.)
2. **Tell the app its address** - in `infrastructure/deploy/.env` on the server:

   ```
   PUBLIC_ORIGIN=https://lpg.vitessetec.com
   SITE_ADDRESS=lpg.vitessetec.com
   ```

   ```bash
   # Recreates only what changed: web (Caddy) and backend/worker (CORS origin).
   cd /opt/lpg-agency/infrastructure/deploy
   cp -p .env ".env.bak-$(date +%F-%H%M)"
   docker compose -f docker-compose.prod.yml up -d
   ```

3. **That is all for the certificate.** With a real hostname in `SITE_ADDRESS`,
   Caddy obtains a Let's Encrypt certificate by itself on start-up (ports 80/443
   are open in the firewall), redirects HTTP to HTTPS (308) and renews it
   automatically about 30 days before expiry. Certificates live in the
   `caddy-data` volume - do not delete that volume. `.env` is not touched by CI
   deploys, so this survives every release.

Verify from any machine:

```bash
curl -sI https://lpg.vitessetec.com/health/live | head -1
echo | openssl s_client -connect lpg.vitessetec.com:443 -servername lpg.vitessetec.com 2>/dev/null | openssl x509 -noout -issuer -dates
```

**Gotchas**
- A DNS lookup made *before* the record existed is cached by resolvers as "no
  such domain" (negative caching) for up to the zone's SOA minimum - possibly
  hours. Create the record first, then look it up. Public resolvers (8.8.8.8,
  1.1.1.1) and Let's Encrypt saw the record immediately.
- Do not probe the site with `http://localhost/...` and `curl -f`: Caddy answers
  any other Host with a 308, which `-f` counts as success. `deploy-image.sh`
  checks the backend container's own health and requires an exact 200 through
  Caddy for the configured site.
- Per-agency subdomains (`<slug>.lpg.vitessetec.com`) need a wildcard DNS record
  and a wildcard certificate, which requires a DNS-provider API for Caddy's
  DNS-01 challenge. cPanel has none usable here; delegating `lpg.vitessetec.com`
  (or a bought domain) to DigitalOcean DNS enables it. Not built yet - see
  ADR-048's note on subdomains.

---

## 9. Day-2 operations

```bash
# Ship an update: pull, rebuild, migrate, restart.
cd /opt/lpg-agency/infrastructure/deploy && ./deploy.sh
```

```bash
# Follow logs (service names: backend, worker, web, postgres, redis, migrate).
docker compose -f docker-compose.prod.yml logs -f --tail=100 backend
```

```bash
# Database backup to a compressed file (copy it off the server too).
mkdir -p /opt/backups
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U lpg_admin lpg | gzip > /opt/backups/lpg-$(date +%F).sql.gz
```

```bash
# Stop / start without losing data (volumes are kept). NEVER add `-v` unless
# you intend to delete the database.
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Troubleshooting

| Symptom | Check |
|---|---|
| Frontend build killed / exits 137 | Out of memory. Confirm swap is on (`swapon --show`), retry. |
| `npm ci` fails with ERESOLVE | Known: `@ngrx/signals@21` vs Angular 22. The frontend Dockerfile already passes `--legacy-peer-deps`. |
| Build: `Cannot find module './prime-license'` | The real key file is git-ignored; the frontend Dockerfile falls back to `prime-license.example.ts` (PrimeNG runs unlicensed). |
| `migrate` exits non-zero | `docker compose -f docker-compose.prod.yml logs migrate` - the first line names the DB target. |
| Backend restarts in a loop | `logs backend` - a missing/invalid secret in `.env` fails loudly at startup. |
| `/health/ready` not OK | Body says which dependency (Postgres/Redis/storage) failed. |
| Changed DB passwords in `.env` and login fails | The Postgres volume keeps the original passwords; restore the old `.env` values. |

---

## 10. How a deployment works (and how to do one by hand)

Nothing is compiled or installed directly on the server. The server holds the
source code (a git clone), a secrets file, and Docker; **everything is built
inside Docker images**.

| Part | Built when | Result |
|---|---|---|
| Angular dashboard | `frontend/Dockerfile`: `npm ci --legacy-peer-deps`, then `nx build dashboard` (TypeScript -> static HTML/JS/CSS) | Files copied into a Caddy image; Caddy serves them and proxies `/api` and `/health` to the backend |
| FastAPI backend | `backend/Dockerfile`: `uv sync --frozen` installs the exact packages from `uv.lock` into a virtualenv; source copied in (Python is not compiled, only byte-code precompiled) | Gunicorn runs it; the background worker uses the same image with a different command |
| Database schema | the `migrate` container runs `alembic upgrade head` on every `up` | Postgres/Redis data lives in Docker volumes and survives redeploys |

Manual deploy, on the droplet (`ssh root@139.59.88.0`):

```bash
# 1. Fetch the new code (read-only GitHub deploy key on this server).
cd /opt/lpg-agency && git pull --ff-only
```

```bash
# 2. (Recommended before schema changes) back up the database.
cd /opt/lpg-agency/infrastructure/deploy
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U lpg_admin lpg | gzip > /opt/backups/lpg-$(date +%F-%H%M).sql.gz
```

```bash
# 3. Build the two images. The Angular build is the slow part (minutes on 1 vCPU).
docker compose -f docker-compose.prod.yml build backend web
```

```bash
# 4. Start the new version: migrations run first, then backend/worker/web are
#    recreated if their image changed. Postgres/Redis are left alone.
docker compose -f docker-compose.prod.yml up -d
```

```bash
# 5. Verify.
docker compose -f docker-compose.prod.yml ps
curl -s http://localhost/health/live
```

`./deploy.sh` performs steps 1, 3, 4 and 5 (it does not take a backup).
For long builds run it detached so a dropped SSH connection cannot kill it:

```bash
nohup ./deploy.sh > /root/deploy.log 2>&1 &
tail -f /root/deploy.log
```

**Rolling back:** `git checkout <previous-commit>` in `/opt/lpg-agency`, then
steps 3-4. Migrations only move forward, so a rollback across a schema change
may also need the step-2 backup restored.

**PrimeNG licence key:** `frontend/apps/dashboard/src/app/prime-license.ts` is
git-ignored and lives only on the server (it is copied to `prime-license.ts`
from `prime-license.example.ts`, then edited). It reaches the browser only when
the web image is rebuilt (step 3). Keep `prime-license.example.ts` in place —
the frontend Dockerfile uses it as a fallback.

---

## 11. Environments

There is **one** environment: the droplet at `139.59.88.0` (`https://lpg.vitessetec.com`), treated as
**production** (`LPG_ENVIRONMENT=production`). It has no real data yet (no
agencies, no licences). A UAT environment was deliberately deferred; when it is
wanted, provision a second droplet with sections 1-9 and `.env.uat.example`, and
add a second GitHub Environment (section 13).

---

## 12. Accounts and access inventory (no secrets)

**This file is committed to git, so it never contains passwords, keys or
tokens** — only which accounts exist and where each secret lives. Keep the
secrets themselves in a password manager.

### Application accounts (production database, as of 2026-09-25)

| Email | Role | Agency | Where the password is |
|---|---|---|---|
| `super_agency@lpg.com` | `super_admin` (Platform Console) | none | Generated by `scripts/bootstrap_super_admin.py` and shown once at creation. Not stored anywhere on the server. **There is no change-password feature yet**, so record it in a password manager. |

No agency admins exist yet; they are created with **Platform Console -> Agencies
-> Create agency**, and each first sets their own password from a one-time link.

### Server and infrastructure access

| What | Who/where | Secret lives in |
|---|---|---|
| SSH to the droplet `root@139.59.88.0` | key `moham@Imran` (ED25519, fingerprint `SHA256:g3LesOLnfXQO+f3FC3mn8S7JpWpJWYF0kzROHlrH7NA`) is the only authorised key | private key `~/.ssh/id_ed25519` on that machine. To add another machine see section 1. |
| Droplet -> GitHub (read-only deploy key "Github - Digital Ocean") | `/root/.ssh/lpg_github_deploy` on the droplet | private key on the droplet only; the public key is registered under the repo's Deploy keys |
| Application secrets | `/opt/lpg-agency/infrastructure/deploy/.env` (mode 600, git-ignored) | that file only — **back it up off-server**: `POSTGRES_ADMIN_PASSWORD`, `LPG_APP_DB_PASSWORD`, `REDIS_PASSWORD`, `LPG_JWT_PRIVATE_KEY`, `LPG_JWT_PUBLIC_KEY`, `LPG_KYC_ENCRYPTION_KEY` (losing this one makes stored KYC data unreadable). `MINIO_*` entries are unused leftovers. |
| Database roles | `lpg_admin` (owner, migrations only) and `lpg_app` (application, no `BYPASSRLS`) inside the Postgres container | passwords in `.env` above |
| PrimeNG licence key | `frontend/apps/dashboard/src/app/prime-license.ts` on the droplet | that file (git-ignored) |
| DigitalOcean account, GitHub account | — | your own logins |

| DNS for `vitessetec.com` (holds the `lpg` A record) | MilesWeb cPanel -> DNS Zone Editor, account `zugjjztt` | your MilesWeb login |
| TLS certificate for `lpg.vitessetec.com` | issued and renewed automatically by Caddy (Let's Encrypt) | `caddy-data` Docker volume |

Not yet configured: object storage credentials (`LPG_STORAGE_*`, a DigitalOcean
Space), any email/SMS provider, a dedicated domain and wildcard certificates.


---

## 13. CI/CD (GitHub Actions -> GHCR -> droplet)

Every merge to `main` deploys to production automatically.

```
push to main
  -> gate-backend  : ruff check, mypy --strict, import-linter, OpenAPI drift, unit tests
  -> gate-frontend : npm ci --legacy-peer-deps, nx lint + test (all projects)
  -> build         : two images, tagged with the commit SHA, pushed to ghcr.io
  -> deploy        : SSH to the droplet -> infrastructure/deploy/deploy-image.sh <sha>
                     (backup DB -> pull images -> migrate -> restart -> health check
                      -> automatic rollback to the previous release if unhealthy)
```

Files: `.github/workflows/deploy.yml`, `.github/workflows/rollback.yml`,
`.github/actions/deploy-to-server/action.yml`,
`infrastructure/deploy/deploy-image.sh`.

**Why the deploy has its own gate instead of waiting on the CI workflows:**
Backend CI and Frontend CI were red on `main` for pre-existing reasons
(repo-wide `ruff format` / `prettier` drift in ~40 and ~190 files, plain
`npm ci` failing on a peer-dependency conflict, no `prime-license.ts`, and a
"design tokens up to date" step that could only fail because `tokens.css` is
hand-maintained). Those were repaired on 2026-09-25 (formatting applied, install
flag and licence template added, the tokens step removed). The deploy gate is a
smaller, faster set of the checks that protect production, so a merge is not
held up by slow or flaky unrelated jobs; once the CI workflows have stayed green
for a while it can be replaced by "wait for CI".

### Security model

- The CI SSH key is **restricted**: in the droplet's `authorized_keys` it is
  prefixed with `restrict,command="/opt/lpg-agency/infrastructure/deploy/deploy-image.sh"`,
  so it can do exactly one thing — run that script — never open a shell.
- `deploy-image.sh` accepts only `deploy <40-hex-sha> <github-user>`, refuses a
  commit that is not on `origin/main`, and takes the registry token on stdin.
- The registry token is the workflow's short-lived `GITHUB_TOKEN`; no long-lived
  registry credential is stored on the server.
- The server's host key is pinned in a GitHub secret (`StrictHostKeyChecking=yes`).

### One-time setup

1. **Create the restricted key pair** (on any machine) and authorise it on the droplet:

   ```bash
   ssh-keygen -t ed25519 -N "" -C lpg-ci-deploy -f ./lpg_ci_deploy
   ```

   ```bash
   # On the droplet: append ONE line to /root/.ssh/authorized_keys.
   echo 'restrict,command="/opt/lpg-agency/infrastructure/deploy/deploy-image.sh" '"$(cat lpg_ci_deploy.pub)" >> /root/.ssh/authorized_keys
   ```

2. **GitHub -> repo -> Settings -> Environments -> New environment `production`**
   (optionally add *Required reviewers* to put a manual approval in front of every deploy).

3. **Add these to the `production` environment** (or as repository secrets):

   | Name | Kind | Value |
   |---|---|---|
   | `DEPLOY_HOST` | variable | `139.59.88.0` |
   | `DEPLOY_SSH_KEY` | secret | contents of the **private** file `lpg_ci_deploy` |
   | `DEPLOY_HOST_KEY` | secret | output of `ssh-keyscan -t ed25519 139.59.88.0` |
   | `PRIME_NG_LICENSE_KEY` | secret | your PrimeNG licence key (optional; without it the site shows the unlicensed banner) |

4. **Bootstrap the server clone onto `main`** (once, after the first merge to `main`),
   because the forced command path lives in the repo checkout:

   ```bash
   cd /opt/lpg-agency && git fetch origin && git checkout -B main origin/main
   ```

5. Delete the private key file from the machine you generated it on once it is in GitHub.

### Day to day

- **Deploy:** merge to `main`. Watch it under the repo's *Actions* tab.
- **Roll back:** Actions -> *Rollback* -> Run workflow -> paste the full SHA of an
  earlier release (images for every merged commit are kept in GHCR). If that
  release changed the schema, also restore the pre-deploy backup from
  `/opt/backups` (the last 14 are kept).
- **See what is running:** `grep IMAGE_TAG /opt/lpg-agency/infrastructure/deploy/.env`
  (the commit SHA).
- **Manual deploy still works:** `./deploy.sh` builds on the server (slow) —
  use `IMAGE_TAG=local ./deploy.sh` so it does not fight CI's tag.
