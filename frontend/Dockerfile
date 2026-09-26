# syntax=docker/dockerfile:1

# Builds the Nx Angular dashboard and serves it with Caddy, which also
# reverse-proxies /api and /health to the backend (see Caddyfile).

FROM node:24-slim AS build
WORKDIR /app

ENV NX_DAEMON=false \
    CI=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NODE_OPTIONS=--max-old-space-size=1536

COPY package.json package-lock.json ./
# --legacy-peer-deps: @ngrx/signals@21 declares an Angular 21 peer range while
# the workspace is on Angular 22, so plain `npm ci` fails with ERESOLVE.
RUN --mount=type=cache,target=/root/.npm npm ci --legacy-peer-deps

COPY . .

# app.config.ts imports the git-ignored ./prime-license (a licence key that is
# never committed). Resolution order:
#   1. a BuildKit secret `prime_ng_license` (CI: `--secret id=prime_ng_license`)
#   2. a prime-license.ts already present in the build context (a server-side
#      manual build where the real file sits next to the source)
#   3. the committed template, which builds PrimeNG unlicensed (banner shown)
# The key ends up in the browser bundle either way - PrimeNG licence keys are
# client-side by design - but a secret mount keeps it out of image history.
# BuildKit does not include a secret's contents in the layer cache key, so a
# cached "no key" layer would be reused after the key is added. CI passes a
# fingerprint (a hash, never the key) as a build-arg; referencing it below busts
# the cache exactly when the key changes.
ARG PRIME_LICENSE_FINGERPRINT=none
RUN --mount=type=secret,id=prime_ng_license \
    echo "licence fingerprint: ${PRIME_LICENSE_FINGERPRINT}" >/dev/null; \
    if [ -s /run/secrets/prime_ng_license ]; then \
      key="$(tr -d '\r\n' < /run/secrets/prime_ng_license)"; \
      printf "export const PRIME_NG_LICENSE_KEY: string | undefined = '%s';\n" "$key" \
        > apps/dashboard/src/app/prime-license.ts; \
    fi
RUN [ -f apps/dashboard/src/app/prime-license.ts ] \
    || cp apps/dashboard/src/app/prime-license.example.ts apps/dashboard/src/app/prime-license.ts

RUN npx nx build dashboard

FROM caddy:2-alpine
COPY --from=build /app/dist/apps/dashboard/browser /srv
COPY Caddyfile /etc/caddy/Caddyfile
