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

  # ---- 4. pull, migrate, restart ---------------------------------------------------
  log "Deploying $sha"
  # Pull BEFORE touching .env: a tag that was never published must fail here,
  # leaving both the running stack and .env exactly as they were.
  IMAGE_TAG="$sha" "${compose[@]}" pull backend web
  set_tag "$sha"
  "${compose[@]}" up -d --remove-orphans

  if healthy; then
    log "Healthy on $sha"
    "${compose[@]}" ps
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
