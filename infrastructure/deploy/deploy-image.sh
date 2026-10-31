#!/usr/bin/env bash
# Deploy a CI-built release: pull prebuilt images for <git-sha>, migrate, restart.
#
# Invoked by CI over SSH through a *restricted* key (authorized_keys forced
# command), so the client's command line arrives in $SSH_ORIGINAL_COMMAND:
#
#     echo "$GHCR_TOKEN" | ssh deploy@host "deploy <git-sha> <ghcr-username>"
#
# Or by hand:  echo "$TOKEN" | ./deploy-image.sh deploy <git-sha> <ghcr-username>
#
# stdin's first line is a short-lived registry token (CI passes GITHUB_TOKEN), so
# no long-lived registry credential is stored on this server.
#
# On failure to become healthy, the previous release is restored. Database
# migrations only move forward, so a rollback across a schema change may need
# the pre-deploy backup restored too (see DEPLOY.md).
set -euo pipefail

# Everything lives inside main(): bash reads a whole function before running it,
# so the `git checkout` below can safely rewrite THIS file mid-run (bash would
# otherwise keep reading a script from a byte offset in the changed file).
main() {

  cd "$(dirname "$0")"
  repo_root="$(cd ../.. && pwd)"

  # ---- inputs (validated: this script runs with root privileges) -----------------
  args="${SSH_ORIGINAL_COMMAND:-$*}"
  read -r verb sha ghcr_user _extra <<<"$args"
  [[ "$verb" == "deploy" ]] || { echo "usage: deploy <git-sha> <ghcr-username>" >&2; exit 2; }
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "refusing: <git-sha> must be a full 40-char commit hash" >&2; exit 2; }
  [[ "$ghcr_user" =~ ^[A-Za-z0-9-]{1,39}$ ]] || { echo "refusing: invalid registry username" >&2; exit 2; }
  [[ -z "${_extra:-}" ]] || { echo "refusing: unexpected extra arguments" >&2; exit 2; }

  IFS= read -r ghcr_token || true
  [[ -n "${ghcr_token:-}" ]] || { echo "refusing: registry token missing on stdin" >&2; exit 2; }
  # Optional line 2: base64 Firebase service-account JSON (empty = keep as is).
  IFS= read -r fcm_b64 || true
  # Optional line 3: base64 LPG_STORAGE_* KEY=VALUE lines (empty = keep as is).
  IFS= read -r storage_b64 || true
  # Optional line 4: base64 LPG_RAZORPAY_* / LPG_PAYMENTS_* KEY=VALUE lines (empty = keep as is).
  IFS= read -r payments_b64 || true

  [[ -f .env ]] || { echo "missing .env - run ./generate-env.sh first" >&2; exit 1; }
  compose=(docker compose -f docker-compose.prod.yml)
  log() { printf '\n==> %s\n' "$*"; }

  # One deploy at a time (CI also serialises, this guards manual overlap).
  exec 9>/var/lock/lpg-deploy.lock
  flock -n 9 || { echo "another deploy is already running" >&2; exit 1; }

  # ---- 1. code that matches the images (compose file, scripts, migrations) ------
  log "Checking out $sha"
  git -C "$repo_root" fetch --quiet origin main
  git -C "$repo_root" cat-file -e "$sha^{commit}" 2>/dev/null \
    || { echo "commit $sha not found after fetching origin/main" >&2; exit 1; }
  git -C "$repo_root" merge-base --is-ancestor "$sha" origin/main \
    || { echo "refusing: $sha is not on origin/main" >&2; exit 1; }
  git -C "$repo_root" checkout --quiet -B main "$sha"

  # ---- 2. registry login (token never touches disk beyond docker's own store) ---
  log "Logging in to ghcr.io as $ghcr_user"
  printf '%s' "$ghcr_token" | docker login ghcr.io -u "$ghcr_user" --password-stdin >/dev/null
  unset ghcr_token

  # ---- 3. backup, then remember what to roll back to -----------------------------
  previous_sha="$(sed -n 's/^IMAGE_TAG=//p' .env | tail -1)"
  log "Backing up the database"
  mkdir -p /opt/backups
  if "${compose[@]}" ps --status running --services 2>/dev/null | grep -qx postgres; then
    "${compose[@]}" exec -T postgres pg_dump -U lpg_admin lpg | gzip \
      > "/opt/backups/lpg-pre-${sha:0:8}-$(date +%F-%H%M%S).sql.gz"
    ls -1t /opt/backups/lpg-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
  else
    echo "postgres is not running - skipping backup"
  fi

  set_tag() {
    if grep -q '^IMAGE_TAG=' .env; then sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$1/" .env; else echo "IMAGE_TAG=$1" >> .env; fi
  }

  # Healthy = the backend container's own health check passes AND a request
  # through Caddy for the configured site returns exactly 200.
  #
  # Do NOT probe `http://localhost/...` with `curl -f`: once SITE_ADDRESS is a
  # real domain, Caddy answers any other Host with a 308 redirect, `-f` treats a
  # 3xx as success, and the check would pass no matter what the backend did -
  # silently disabling the automatic rollback.
  healthy() {
    local site backend_id url resolve=()
    site="$(sed -n 's/^SITE_ADDRESS=//p' .env | tail -1)"
    if [[ -z "$site" || "$site" == :* ]]; then
      url="http://localhost/health/live"
    else
      url="https://${site}/health/live"
      resolve=(--resolve "${site}:443:127.0.0.1")
    fi
    for _ in $(seq 1 30); do
      backend_id="$("${compose[@]}" ps -q backend 2>/dev/null || true)"
      if [[ -n "$backend_id" ]]         && [[ "$(docker inspect -f '{{.State.Health.Status}}' "$backend_id" 2>/dev/null)" == "healthy" ]]         && [[ "$(curl -s -k -m 5 "${resolve[@]}" -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)" == "200" ]]; then
        return 0
      fi
      sleep 2
    done
    return 1
  }

  # Writes LPG_FCM_CREDENTIALS_JSON / LPG_FCM_PROJECT_ID into integrations.env,
  # replacing any earlier (or commented-out) lines for them. The JSON is
  # single-quoted so compose takes it literally (no $ or \ processing).
  install_fcm_credentials() {
    local json project_id tmp
    json="$(printf '%s' "$1" | base64 -d 2>/dev/null | python3 -c '
import json, sys
sa = json.load(sys.stdin)
assert sa.get("type") == "service_account" and sa.get("client_email") and sa.get("private_key")
print(json.dumps(sa, separators=(",", ":")))
' 2>/dev/null)" || { echo "!! FCM service account is not a valid service-account JSON - push settings left unchanged" >&2; return 0; }
    [[ "$json" != *"'"* ]] || { echo "!! FCM service account contains a single quote - push settings left unchanged" >&2; return 0; }
    project_id="$(printf '%s' "$json" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("project_id", ""))')"
    touch integrations.env && chmod 600 integrations.env
    tmp="$(mktemp integrations.env.XXXXXX)"
    grep -vE '^[[:space:]]*#?[[:space:]]*LPG_FCM_(CREDENTIALS_JSON|CREDENTIALS_PATH|PROJECT_ID)=' integrations.env > "$tmp" || true
    printf "LPG_FCM_PROJECT_ID=%s\nLPG_FCM_CREDENTIALS_JSON='%s'\n" "$project_id" "$json" >> "$tmp"
    chmod 600 "$tmp" && mv "$tmp" integrations.env
    echo "FCM credentials installed for Firebase project $project_id"
  }

  # Upserts the LPG_STORAGE_* settings into .env (compose interpolates them into
  # the backend's environment). Only the five known keys are accepted, and a value
  # with a quote, backslash, space or $ is refused so .env stays parseable.
  install_storage_settings() {
    local decoded line key value tmp
    decoded="$(printf '%s' "$1" | base64 -d 2>/dev/null)" \
      || { echo "!! storage settings are not valid base64 - left unchanged" >&2; return 0; }
    tmp="$(mktemp .env.XXXXXX)"
    cp .env "$tmp"
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      key="${line%%=*}"; value="${line#*=}"
      case "$key" in
        LPG_STORAGE_ENDPOINT_URL|LPG_STORAGE_ACCESS_KEY|LPG_STORAGE_SECRET_KEY|LPG_STORAGE_BUCKET|LPG_STORAGE_REGION) ;;
        *) echo "!! unexpected storage key - settings left unchanged" >&2; rm -f "$tmp"; return 0 ;;
      esac
      if [[ -z "$value" || "$value" =~ [[:space:]\"\'\\\$] ]]; then
        echo "!! invalid value for $key - settings left unchanged" >&2; rm -f "$tmp"; return 0
      fi
      if grep -q "^${key}=" "$tmp"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$tmp"
      else
        printf '%s=%s\n' "$key" "$value" >> "$tmp"
      fi
    done <<<"$decoded"
    chmod 600 "$tmp" && mv "$tmp" .env
    echo "storage: object storage settings installed"
  }

  # Writes the Razorpay settings into integrations.env, replacing earlier (or
  # commented-out) lines for the same keys. Only the known keys are accepted,
  # and a value with a quote, backslash, space or $ is refused.
  install_payments_settings() {
    local decoded line key value tmp
    decoded="$(printf '%s' "$1" | base64 -d 2>/dev/null)" \
      || { echo "!! payments settings are not valid base64 - left unchanged" >&2; return 0; }
    touch integrations.env && chmod 600 integrations.env
    tmp="$(mktemp integrations.env.XXXXXX)"
    cp integrations.env "$tmp"
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      key="${line%%=*}"; value="${line#*=}"
      case "$key" in
        LPG_PAYMENTS_PROVIDER|LPG_PAYMENTS_ALLOW_TEST_KEYS|LPG_RAZORPAY_KEY_ID|LPG_RAZORPAY_KEY_SECRET|LPG_RAZORPAY_WEBHOOK_SECRET) ;;
        *) echo "!! unexpected payments key - settings left unchanged" >&2; rm -f "$tmp"; return 0 ;;
      esac
      if [[ -z "$value" || "$value" =~ [[:space:]\"\'\\\$] ]]; then
        echo "!! invalid value for $key - settings left unchanged" >&2; rm -f "$tmp"; return 0
      fi
      grep -vE "^[[:space:]]*#?[[:space:]]*${key}=" "$tmp" > "$tmp.new" || true
      printf '%s=%s\n' "$key" "$value" >> "$tmp.new"
      mv "$tmp.new" "$tmp"
    done <<<"$decoded"
    chmod 600 "$tmp" && mv "$tmp" integrations.env
    echo "payments: Razorpay settings installed"
  }

  # Which push channel the worker built at startup (no secrets in these lines).
  report_push_status() {
    local status
    status="$("${compose[@]}" logs --no-color worker 2>/dev/null \
      | grep -oE 'fcm_push_channel_enabled|fcm_credentials_[a-z_]+' | tail -1 || true)"
    case "$status" in
      fcm_push_channel_enabled) echo "push: FCM enabled" ;;
      "") echo "push: not configured (stub channel, nothing is delivered)" ;;
      *) echo "!! push: FCM misconfigured ($status) - stub channel in use" >&2 ;;
    esac
  }

  # ---- 4. pull, migrate, restart ---------------------------------------------------
  log "Deploying $sha"
  # Pull BEFORE touching .env: a tag that was never published must fail here,
  # leaving both the running stack and .env exactly as they were.
  # Old release images pile up (one tag per merge) and filled the droplet disk
  # (deploy 40940590585: "no space left on device"). Images in use by running
  # containers are kept, so the running release stays available for rollback.
  docker image prune -af >/dev/null || true
  docker builder prune -af >/dev/null || true
  IMAGE_TAG="$sha" "${compose[@]}" pull backend web
  set_tag "$sha"
  if [[ -n "${fcm_b64:-}" ]]; then
    install_fcm_credentials "$fcm_b64"
  fi
  unset fcm_b64
  if [[ -n "${storage_b64:-}" ]]; then
    install_storage_settings "$storage_b64"
  fi
  unset storage_b64
  if [[ -n "${payments_b64:-}" ]]; then
    install_payments_settings "$payments_b64"
  fi
  unset payments_b64
  "${compose[@]}" up -d --remove-orphans

  if healthy; then
    log "Healthy on $sha"
    "${compose[@]}" ps
    sleep 5
    report_push_status
    docker image prune -f >/dev/null
    exit 0
  fi

  # ---- 5. rollback ---------------------------------------------------------------
  echo "!! $sha did not become healthy" >&2
  "${compose[@]}" logs --tail 40 backend >&2 || true
  if [[ -n "$previous_sha" && "$previous_sha" != "$sha" && "$previous_sha" != "local" ]]; then
    log "Rolling back to $previous_sha"
    git -C "$repo_root" checkout --quiet -B main "$previous_sha" || true
    set_tag "$previous_sha"
    "${compose[@]}" up -d --remove-orphans
    healthy && echo "rolled back to $previous_sha" >&2 || echo "!! rollback is ALSO unhealthy - manual intervention needed" >&2
  else
    echo "no previous release to roll back to" >&2
  fi
  exit 1
}

main "$@"
exit $?
