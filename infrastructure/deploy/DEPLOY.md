# Deploying LPG Agency to a DigitalOcean Droplet

Single-host Docker Compose deployment: Postgres 17, Redis, the FastAPI backend, the arq background worker, a one-shot Alembic
migration job, and Caddy serving the Angular dashboard and reverse-proxying
`/api` + `/health` to the backend (same origin, so no CORS in practice).

| Item | Value |
|---|---|
| Droplet public IP | `139.59.88.0` |
| OS | Ubuntu 24.04 LTS, 1 vCPU, 2 GB RAM, 48 GB disk |
| SSH user | `root` (key auth only) |
| App directory | `/opt/lpg-agency` |
| Compose project | `lpg-agency` (files in `infrastructure/deploy/`) |

> **Status (2026-09-25).** Sections 1-6 were executed and verified: the stack
> deploys, all 86 migrations apply, the dashboard loads at `http://139.59.88.0/`
> and `/health/live` returns 200. `/health/ready` returns 503 only because
> object storage is not configured yet (see "Object storage" in section 5).
> Sections 7-8 (first admin user, HTTPS) are still open.

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

## 7. First admin user (OPEN ITEM)

A fresh database has no tenant or users. The existing seed scripts
(`backend/scripts/seed_dev_user.py`) create **well-known dev credentials**
(`admin@example.com` / `correct-horse-battery`) and must not be used as-is on a
real server. A production bootstrap for the first tenant/`super_admin` still
needs to be decided and written.

---

## 8. HTTPS once you have a domain

1. Point an `A` record for the domain at `139.59.88.0`.
2. Edit `infrastructure/deploy/.env`:
   ```
   PUBLIC_ORIGIN=https://app.example.com
   SITE_ADDRESS=app.example.com
   ```
3. Restart the web container so Caddy obtains a Let's Encrypt certificate:
   ```bash
   cd /opt/lpg-agency/infrastructure/deploy
   docker compose -f docker-compose.prod.yml up -d web backend worker
   ```

Ports 80 and 443 are already open in the firewall.

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
