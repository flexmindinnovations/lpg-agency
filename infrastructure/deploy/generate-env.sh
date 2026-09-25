#!/usr/bin/env bash
# Writes infrastructure/deploy/.env with freshly generated secrets.
# Refuses to overwrite an existing .env — rotating secrets on a live database
# would lock the app out of Postgres (the volume keeps the ORIGINAL passwords).
#
#   ./generate-env.sh                      # PUBLIC_ORIGIN defaults to http://<droplet public IP>
#   ./generate-env.sh https://app.example.com app.example.com
#                     ^ PUBLIC_ORIGIN       ^ SITE_ADDRESS (enables automatic HTTPS)
set -euo pipefail
cd "$(dirname "$0")"

if [ -e .env ]; then
  echo ".env already exists - refusing to overwrite. Delete it deliberately if you really want new secrets." >&2
  exit 1
fi

public_ip="$(curl -fsS https://api.ipify.org || true)"
public_origin="${1:-http://${public_ip:-localhost}}"
site_address="${2:-:80}"

hex() { openssl rand -hex 24; }

tmp="$(mktemp)"; trap 'rm -f "$tmp" "$tmp.pub"' EXIT
openssl genrsa -out "$tmp" 2048 2>/dev/null
openssl rsa -in "$tmp" -pubout -out "$tmp.pub" 2>/dev/null
# .env is single-line-per-value; the backend un-escapes literal \n back to newlines.
private_pem="$(awk 'BEGIN{ORS="\\n"} {print}' "$tmp")"
public_pem="$(awk 'BEGIN{ORS="\\n"} {print}' "$tmp.pub")"
# A Fernet key is 32 random bytes, url-safe base64.
fernet_key="$(openssl rand -base64 32 | tr '+/' '-_')"

umask 077
cat > .env <<EOF
PUBLIC_ORIGIN=${public_origin}
SITE_ADDRESS=${site_address}

POSTGRES_ADMIN_PASSWORD=$(hex)
LPG_APP_DB_PASSWORD=$(hex)
REDIS_PASSWORD=$(hex)

LPG_JWT_PRIVATE_KEY='${private_pem}'
LPG_JWT_PUBLIC_KEY='${public_pem}'
LPG_KYC_ENCRYPTION_KEY=${fernet_key}

# S3-compatible object storage (e.g. DigitalOcean Spaces). Fill these in, then
# `docker compose -f docker-compose.prod.yml up -d backend worker`.
LPG_STORAGE_ENDPOINT_URL=
LPG_STORAGE_ACCESS_KEY=
LPG_STORAGE_SECRET_KEY=
LPG_STORAGE_BUCKET=
LPG_STORAGE_REGION=
EOF

echo "Wrote $(pwd)/.env (mode 600). Back this file up somewhere safe: losing the"
echo "encryption key makes stored KYC data unreadable, and the DB passwords are"
echo "baked into the Postgres volume."
